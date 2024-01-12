# 操作android手机QQ，按条件查找好友，并获得好友信息

import os, sys, time, signal
import cv2
import sys
import json
import re
import xml.etree.ElementTree as ET

from and_controller import list_all_devices, AndroidController, traverse_tree, execute_adb
from config import load_config
from utils import print_with_color, draw_bbox_multi


configs = load_config()

# 函数：获得设备名称
def get_device_name():
    device_list = list_all_devices()
    if not device_list:
        print_with_color("ERROR: No device found!", "red")
        return
    if len(device_list) == 1:
        return device_list[0]
    print_with_color("Which device do you want to use?", "blue")
    for i, d in enumerate(device_list):
        print_with_color(f"{i + 1}. {d}", "blue")
    num = input()
    if not re.match(r"^\d+$", num):
        print_with_color("ERROR: Invalid input!", "red")
        exit()
    device_index = int(num) - 1
    return device_list[device_index]

# 类：获得QQ好友信息
class QQFriendsExplorer:
    def __init__(self, device_name, save_dir):
        self.device_name = device_name
        self.controller = AndroidController(device_name)
        self.backslash = "\\"
        self.save_dir = save_dir
        self.xml_save_dir = os.path.join(save_dir, "xml")
        if not os.path.exists(self.xml_save_dir):
            os.mkdir(self.xml_save_dir)
        self.png_save_dir = os.path.join(save_dir, "png")
        if not os.path.exists(self.png_save_dir):
            os.mkdir(self.png_save_dir)
        self.step = 0
        # 已经探索过的好友，避免重复探索
        self.explored_friends = []

    ############################################
    # 函数：查找符合条件的元素
    # @param xml_path: xml文件路径
    # @param elem_list: 元素列表
    # @param attrib: 元素属性, 如resource-id\text\content-desc等
    # @param conditions: 元素属性值
    def find_elements(self, xml_path, elem_list, attrib, conditions):
        # 查找text为“查找”的元素
        for event, elem in ET.iterparse(xml_path, ['start', 'end']):
            if event == 'start':
                if elem.attrib.get(attrib) == conditions:
                    elem_list.append(elem)
        return elem_list
    
    ############################################
    # 函数：返回元素的bbox
    # @param elem: 元素
    # @return: 元素的bbox
    def get_element_bbox(self, elem):
        bounds = elem.attrib["bounds"][1:-1].split("][")
        x1, y1 = map(int, bounds[0].split(","))
        x2, y2 = map(int, bounds[1].split(","))
        return x1, y1, x2, y2
    
    ############################################
    # 函数：返回元素的中心坐标（x, y）
    # @param elem: 元素
    # @return: 元素的中心坐标（x, y）
    def get_element_center(self, elem):
        x1, y1, x2, y2 = self.get_element_bbox(elem)
        # 返回值取整
        return (x1 + x2) // 2, (y1 + y2) // 2
    
    ############################################
    # 函数：读取xml，处理类似命名这些细节
    # 返回值：xml文件路径
    def read_xml(self):
        # 获得xml，保存到save_dir/# 日期+时间+step.xml
        datetime = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        prefix =  f"{datetime}_{self.step:03d}"
        xml_path = self.controller.get_xml(prefix, self.xml_save_dir)
        return xml_path

    ############################################
    # read all text and content-desc from xml file
    # @param xml_path: xml file path
    # @param content_list: content list
    # @return: content list
    def read_text(self, xml_path, content_list):
        for event, elem in ET.iterparse(xml_path, ['start', 'end']):
            if event == 'start':
                if elem.attrib.get("content-desc"):
                    # 如果content_list中存在相同的content-desc，则不添加
                    content_desc = f"content-desc: {elem.attrib['content-desc']}\n"
                    if content_desc not in content_list:
                        content_list.append(content_desc)
                if elem.attrib.get("text"):
                    # 如果content_list中存在相同的content-desc，则不添加
                    text = f"text: {elem.attrib['text']}\n"
                    if text not in content_list:
                        content_list.append(text)
        return content_list

    ############################################
    # 函数：读取指定元素的图片
    # @param elem: 元素
    # @param save_path: 保存路径
    # @param prefix: 图片名称前缀
    # @return: 图片的image
    def read_element_image(self, elem, prefix, save_path):
        x1, y1, x2, y2 = self.get_element_bbox(elem)
        # 截取图片
        png_on_local = self.controller.get_screenshot(prefix, save_path)
        if not png_on_local:
            print_with_color("ERROR: 截取图片失败！", "red")
            return False
        
        image = cv2.imread(png_on_local)
        # 裁剪图片
        image = image[y1:y2, x1:x2]
        # 删除原图片
        os.remove(png_on_local)
        # 写入新图片
        ret = cv2.imwrite(png_on_local, image)
        if not ret:
            print_with_color("ERROR: 保存图片失败！", "red")
            return False
        print_with_color(f"图片保存到: {png_on_local}", "yellow")
        return image
        
    ############################################
    # 函数：点击查询QQ好友列表
    # @return: 点击成功返回True，否则返回False
    def query_qq_friends(self):
        self.step += 1
        print_with_color(f"Step {self.step}: 点击查询QQ好友列表", "blue")

        # 获得xml
        xml_path = self.read_xml()

        # 查找text为“查找”的元素
        elem_list = []
        self.find_elements(xml_path, elem_list, "text", "查找")
        if not elem_list:
            print_with_color("ERROR: No element found!", "red")
            return
        
        # 点击查找按钮
        search_btn = elem_list[0]
        x,y = self.get_element_center(search_btn)
        print_with_color(f"点击查找按钮：{x}, {y}", "yellow")
        ret = self.controller.tap(x, y)

        print_with_color("OK!", "green")
        return True
        
    ############################################        
    # 函数：从页面上获取待探索的好友列表
    # @return: 待探索的好友列表
    def get_friend_list(self):
        self.step += 1
        print_with_color(f"Step {self.step}: 从页面上获取待探索的好友列表", "blue")

        # 获得xml
        xml_path = self.read_xml()

        friend_elem_list = []
        # 搜索resource-id="com.tencent.mobileqq:id/f9r"的元素列表
        self.find_elements(xml_path, friend_elem_list, "resource-id", "com.tencent.mobileqq:id/f9r")
        if not friend_elem_list:
            print_with_color("ERROR: No element found!", "red")
            return
        
        # 遍历元素列表获得好友昵称，如果好友昵称已经探索过，则从列表中删除
        friend_list = []
        for friend_elem in friend_elem_list:
            friend_name = friend_elem.attrib["text"]
            if friend_name not in self.explored_friends:
                friend_list.append(friend_elem)
            else:
                print_with_color(f"好友{friend_name}已经探索过，跳过", "yellow")

        print_with_color(f"共有: {len(friend_list)} 个待探索的好友", "yellow")
        # 返回待探索的好友列表
        return friend_list

    ############################################
    # 函数：获得QQ好友信息
    # @param friend_nickname: 好友昵称
    # @return: qq号, 好友信息
    def get_friend_info(self, friend_nickname):
        self.step += 1
        print_with_color(f"Step {self.step}: 获得QQ好友信息", "blue")

        # 先获得设备中心坐标
        width, height = self.controller.get_device_size()
        x, y = width // 2, height // 2

        print_with_color(f"正在读取好友:\"{friend_nickname}\"的信息", "yellow")
        cycle = 0
        content_list = []
        while(cycle < 2):
            # 获得xml
            xml_path = self.read_xml()
            # 读取全部文本信息
            self.read_text(xml_path, content_list)

            # 往下翻动页面，看是不是能找到更多信息
            # 翻动页面(quickly)
            ret = self.controller.swipe(x, y, "up", "long", True)  
            if (ret == "ERROR"):
                print_with_color("ERROR: 翻动页面失败！", "red")
                continue
            cycle += 1

        # 回到顶部
        ret = self.controller.swipe(x, y, "down", "long", True)
        time.sleep(1)

        # 在content_list中查找类似 QQ号：3207497515 的信息，并提取QQ号（数字）
        qq_num = ""
        for content in content_list:
            if "QQ号" in content:
                qq_num = re.findall(r"\d+", content)[0]
                break
        if not qq_num:
            print_with_color("ERROR: 未找到QQ号！", "red")
            return
        else:
            print_with_color(f"正在读取好友\"{friend_nickname}\"(QQ:{qq_num})的头像", "yellow")
            # 重新读取xml
            xml_path = self.read_xml()

            # 获取查看大头像 elment_id=com.tencent.mobileqq:id/dk3 的元素
            elem_list = []
            self.find_elements(xml_path, elem_list, "resource-id", "com.tencent.mobileqq:id/dk3")
            if not elem_list:
                time.sleep(1)
                print_with_color("ERROR: No element found!", "red")
                return
            
            # 获得元素x, y坐标
            x, y = self.get_element_center(elem_list[0])
            # 点击查看大头像
            print_with_color(f"点击查看大头像：{x}, {y}", "yellow")
            ret = self.controller.tap(x, y)
            if ret == "ERROR":
                print_with_color("ERROR: 点击查看大头像失败！", "red")
                return
            # 休息1秒等待页面加载完成
            time.sleep(1)
            # 获得xml
            xml_path = self.read_xml()
            # 查找resource-id="com.tencent.mobileqq:id/image"的元素列表
            elem_list = []
            self.find_elements(xml_path, elem_list, "resource-id", "com.tencent.mobileqq:id/image")
            if not elem_list:
                print_with_color("ERROR: No element found!", "red")
                return
            # 读取图片
            prefix = f"{qq_num}"
            image = self.read_element_image(elem_list[0], prefix, self.png_save_dir)
            if isinstance(image, bool) and image == False:
                print_with_color("ERROR: 读取图片失败！", "red")
                # 返回
                self.controller.back()
                time.sleep(1)
                return
            # 显示图片
            cv2.imshow("image", image)
            cv2.waitKey(100)
            cv2.destroyAllWindows()
            # 返回
            ret = self.controller.back()
            time.sleep(1)
        # 构造打印信息
        friend_info_text = "\n".join(content_list)
        return {
            "qq": qq_num,
            "introduction": friend_info_text
        }
        
    ############################################
    # 函数：获得QQ好友头像
        
    ############################################
    # 函数：开始探索QQ好友信息
    def start_exploring(self):
        # 点击查询QQ好友列表
        self.query_qq_friends()
        # 从页面上获取待探索的好友列表
        friend_list = self.get_friend_list()
        if not friend_list:
            print_with_color("ERROR: No friend found!", "red")
            return
        # 休息1秒等待页面加载完成
        time.sleep(1)
        
        # 遍历好友列表，获得好友信息
        for friend_elem in friend_list:
            # 获得坐标
            x, y = self.get_element_center(friend_elem)
            # 点击好友
            print_with_color(f"点击好友：{x}, {y}", "yellow")
            ret = self.controller.tap(x, y)
            if ret == "ERROR":
                print_with_color("ERROR: 点击好友失败！", "red")
                continue

            # 休息1秒等待页面加载完成
            time.sleep(1)

            # 获得QQ好友信息
            friend_name = friend_elem.attrib["text"]
            friend_info = self.get_friend_info(friend_name)
            if not friend_info:
                # back
                print_with_color("ERROR: 获得QQ好友信息失败！", "red")
                ret = self.controller.back()
                time.sleep(1)

                continue
            print_with_color(friend_info["introduction"], "yellow")

            # 将好友添加到已探索列表           
            self.explored_friends.append(friend_name)
            print_with_color(f"好友\"{friend_name}\", QQ: {friend_info['qq']} 探索完成", "yellow")

            # back
            ret = self.controller.back()
            if ret == "ERROR":
                print_with_color("ERROR: 返回失败！", "red")
                continue
            time.sleep(1)
        
        print_with_color("OK!", "green")
        return True


def signal_handler(sig, frame):
    print_with_color("You pressed ^C, Exit!", "blue")
    sys.exit(0)

if __name__ == "__main__":
    # 订阅^C信号
    signal.signal(signal.SIGINT, signal_handler)
    # 获得设备名称
    device_name = get_device_name()
    if not device_name:
        sys.exit()
    print_with_color(f"Device selected: {device_name}", "yellow")

    # 设置工作目录
    current_module_path = os.path.dirname(os.path.abspath(__file__))
    work_dir = os.path.join(current_module_path, "../qq_friends_explorer")
    if not os.path.exists(work_dir):
        os.mkdir(work_dir)
    # 设置job目录
    # job的命名为：job_日期+时间
    datetime = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
    job_name = f"job_{datetime}"
    job_dir = os.path.join(work_dir, job_name)
    if not os.path.exists(job_dir):
        os.mkdir(job_dir)

    # 获得QQ好友信息
    qq_friends_explorer = QQFriendsExplorer(device_name, job_dir)
    qq_friends_explorer.start_exploring()
    



