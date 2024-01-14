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
from qq_friends import QQFriends


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
    def __init__(self, device_name, save_dir, explore_condition=""):
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
        self.explored_friends_info = []
        # 获得QQ好友数据库
        self.qq_friends = QQFriends()
        # 尝试获取已经存在数据库中的QQ好友的次数
        self.try_get_friend_count = 0
        self.explore_condition = explore_condition

    ############################################
    # 函数：重置已经探索过的好友列表
    def reset_explored_friends(self):
        self.explored_friends = []
        self.explored_friends_info = []

    def get_try_friend_repetitive_count(self):
        return self.try_get_friend_count

    ############################################
    # 函数：tap一个符合条件的元素
    # @attrib: 元素属性, 如resource-id\text\content-desc等
    # @conditions: 元素属性值
    # @return: 点击成功返回True，否则返回False
    def tap_element(self, attrib, conditions):
        try:
            # 获得xml
            xml_path = self.read_xml()
            if xml_path == "ERROR":
                print_with_color("ERROR: 读取xml失败！", "red")
                return False

            # 查找text为“查找”的元素
            elem_list = []
            self.find_elements(xml_path, elem_list, attrib, conditions)
            if not elem_list:
                print_with_color("ERROR: No element found!", "red")
                return False
            
            # 点击查找按钮
            x,y = self.get_element_center(elem_list[0])
            ret = self.controller.tap(x, y)
            if ret == "ERROR":
                print_with_color("ERROR: 点击查找按钮失败！", "red")
                return False
            return True
        except Exception as e:
            print_with_color(f"ERROR: 点击查找按钮失败！{e}", "red")
            return False
        
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
        if xml_path == "ERROR":
            print_with_color("ERROR: 读取xml失败！", "red")
            return False

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
        friend_elem_list = []

        print_with_color(f"Step {self.step}: 从页面上获取待探索的好友列表", "blue")

        # 获得xml
        xml_path = self.read_xml()
        if xml_path == "ERROR":
            print_with_color("ERROR: 读取xml失败！", "red")
            return friend_elem_list

        
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

    def find_qq_number_from_content_list(self, content_list):
        for content in content_list:
            if "QQ号" in content:
                qq_num = re.findall(r"\d+", content)[0]
                return qq_num
            # 或者一串纯数字，长度大于6
            else:
                s = re.search(r"\d{6,}", content)
                if s:
                    qq_num = s.group(0)
                    return qq_num
        return ""
    
    def raise_if_qq_number_exists(self, qq_num):
        if self.qq_friends.qq_number_exists(qq_num):
            print_with_color(f"QQ号{qq_num}已经存在数据库中，跳过", "yellow")
            self.try_get_friend_count += 1
            raise Exception(f"QQ号{qq_num}已经存在数据库中，跳过")
    
    ############################################
    # 函数：获得QQ好友信息
    # @param friend_nickname: 好友昵称
    # @return: qq号, 好友信息
    def get_friend_info(self, friend_nickname):
        self.step += 1
        print_with_color(f"Step {self.step}: 获得QQ好友信息", "blue")
        # 打印当前尝试获取已经存在数据库中的QQ好友的次数
        print_with_color(f"尝试获取已经存在数据库中的QQ好友的次数: {self.try_get_friend_count}", "blue")

        # 先获得设备中心坐标
        width, height = self.controller.get_device_size()
        x, y = width // 2, height // 2

        print_with_color(f"正在读取好友:\"{friend_nickname}\"的信息", "yellow")
        cycle = 0
        content_list = []
        qq_num = ""
        while(cycle < 3):
            # 获得xml
            xml_path = self.read_xml()
            if xml_path == "ERROR":
                print_with_color("ERROR: 读取xml失败！", "red")
                raise Exception("ERROR: 读取xml失败！")
            # 读取全部文本信息
            try:
                self.read_text(xml_path, content_list)
                if not qq_num:
                    qq_num = self.find_qq_number_from_content_list(content_list)
            except:
                print_with_color("ERROR: 读取文本信息失败！", "red")
                raise Exception("ERROR: 读取文本信息失败！")
            
            if qq_num:
                self.raise_if_qq_number_exists(qq_num)

            # 往下翻动页面，看是不是能找到更多信息
            self.controller.swipe(x, y, "up", "long", False)
            cycle += 1

        # 回到顶部
        ret = self.controller.swipe(x, y, "down", "long", True)
        time.sleep(1)

        # 如果前期没有找到QQ号，则再次尝试
        if not qq_num:
            qq_num = self.find_qq_number_from_content_list(content_list)
        if not qq_num:
            print_with_color("ERROR: 未找到QQ号！", "red")
            raise Exception("ERROR: 未找到QQ号！")
        
        # 判断QQ号是否已经在数据库中存储过，如果是，则直接返回，并增加重试计数器
        self.raise_if_qq_number_exists(qq_num)
        
        # 获得QQ好友头像
        png_save_path = self.get_friend_avatar(friend_nickname, qq_num)

        # 构造打印信息
        friend_info_text = "\n".join(content_list)
        friend_info = {
            "qq": qq_num,
            "nickname": friend_nickname,
            "introduction": friend_info_text,
            "pic_path": png_save_path
        }
        self.explored_friends_info.append(friend_info)
        return friend_info
        
    ############################################
    # 函数：获得QQ好友头像
    # @param friend_nickname: 好友昵称
    # @param qq_num: 好友QQ号
    # @return: 图片的存储路径
    def get_friend_avatar(self, friend_nickname, qq_num):
        print_with_color(f"正在读取好友\"{friend_nickname}\"(QQ:{qq_num})的头像", "yellow")
        # 重新读取xml
        xml_path = self.read_xml()
        if xml_path == "ERROR":
            print_with_color("ERROR: 读取xml失败！", "red")
            return

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

        try:
            # 获得xml
            xml_path = self.read_xml()
            if xml_path == "ERROR":
                print_with_color("ERROR: 读取xml失败！", "red")
                raise Exception("ERROR: 读取xml失败！")
                
            # 查找resource-id="com.tencent.mobileqq:id/image"的元素列表
            elem_list = []
            self.find_elements(xml_path, elem_list, "resource-id", "com.tencent.mobileqq:id/image")
            if not elem_list:
                print_with_color("ERROR: No element found!", "red")
                raise Exception("ERROR: No element found!")
            
            # 读取图片
            prefix = f"{qq_num}"
            image = self.read_element_image(elem_list[0], prefix, self.png_save_dir)
            if isinstance(image, bool) and image == False:
                print_with_color("ERROR: 读取图片失败！", "red")
                raise Exception("ERROR: 读取图片失败！")
            
            # 显示图片
            # cv2.imshow("image", image)
            # cv2.waitKey(100)
            # cv2.destroyAllWindows()
            # 返回
            ret = self.controller.back()
            time.sleep(1)

            return f"{self.png_save_dir}/{qq_num}.png"
        except:
            print_with_color("ERROR: 读取大头帖失败！", "red")
            # 返回
            self.controller.back()
            time.sleep(1)
            return
        
    ############################################
    # 函数：初始化到准备查找QQ好友的页面
    # @return: 初始化成功返回True，否则返回False
    def init_to_find_qq_friends(self):
        self.step += 1
        try:
            # 重启qq
            # stop qq: adb shell am force-stop com.tencent.mobileqq
            execute_adb(f"adb -s {self.device_name} shell am force-stop com.tencent.mobileqq")
            time.sleep(5)
            # adb shell am start -n com.tencent.mobileqq/.activity.SplashActivity
            execute_adb(f"adb -s {self.device_name} shell am start -n com.tencent.mobileqq/.activity.SplashActivity")
            time.sleep(3)

            # 点击加号
            # 快捷入口 resource_id=com.tencent.mobileqq:id/ba3(点+号)
            ret = self.tap_element("resource-id", "com.tencent.mobileqq:id/ba3")
            if not ret:
                print_with_color("ERROR: 点击加号失败！", "red")
                raise Exception("ERROR: 点击加号失败！")
            time.sleep(1)

            # text="加好友/群"（点击加好友/群）
            ret = self.tap_element("text", "加好友/群")
            if not ret:
                print_with_color("ERROR: 点击加好友/群失败！", "red")
                raise Exception("ERROR: 点击加好友/群失败！")
            time.sleep(1)

            # text="条件查找"（点击条件查找）
            ret = self.tap_element("text", "条件查找")
            if not ret:
                print_with_color("ERROR: 点击条件查找失败！", "red")
                raise Exception("ERROR: 点击条件查找失败！")
            time.sleep(1)
            return True
        except Exception as e:
            print_with_color(f"ERROR: 初始化到准备查找QQ好友的页面失败！{e}", "red")
            return False

    ############################################
    # 函数：获取当前橱窗的好友信息
    # @return: 返回获得的好友数量
    def get_current_window_friend_info(self):
        count = 0
        self.step += 1
        print_with_color(f"Step {self.step}: 获取当前橱窗的好友信息", "blue")

        # 从页面上获取待探索的好友列表
        # 这里已经跳过了已经探索过的好友
        friend_list = self.get_friend_list()

        if not friend_list:
            print_with_color("ERROR: No friend found!", "red")
            return count
        # 休息1秒等待页面加载完成
        time.sleep(1)
        
        # 遍历好友列表，获得好友信息
        for friend_elem in friend_list:
            friend_name = friend_elem.attrib["text"]
            # 无论何种原因，都将好友添加到已探索列表           
            self.explored_friends.append(friend_name)

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
            try:
                friend_info = self.get_friend_info(friend_name)
                # 添加到数据库中
                # 如果QQ号不存在，则插入QQ好友数据库
                qq_mumber = friend_info["qq"]
                if not self.qq_friends.qq_number_exists(qq_mumber):
                    print_with_color(f"QQ号{qq_mumber}不存在，插入QQ好友数据库", "yellow")
                    try:
                        to_save = {
                            "QQNumber": qq_mumber,
                            "Nickname": friend_info["nickname"],
                            "ExploreCondition": self.explore_condition
                        }
                        self.extract_friend_info(friend_info["introduction"], to_save)
                        self.qq_friends.add_friend(to_save)
                        self.qq_friends.add_friend_detail(qq_mumber, {
                            "Description": friend_info["introduction"],
                            "PhotoPath": friend_info["pic_path"]
                        })
                    except Exception as e:
                        print_with_color(f"ERROR: 插入QQ好友数据库失败！{e}", "red")
                        raise Exception(f"ERROR: 插入QQ好友数据库失败！")
            except Exception as e:
                print_with_color(f"ERROR: 获取QQ好友\"{friend_name}\"失败{e}", "red")
                # back
                self.controller.back()
                time.sleep(1)
                continue
            
            # 如果成功，打印好友信息
            print_with_color(friend_info["introduction"], "yellow")
            print_with_color(f"好友\"{friend_name}\", QQ: {friend_info['qq']} 探索完成", "yellow")

            # back
            self.controller.back()
            time.sleep(1)

            # 获得的好友数量+1
            count += 1
        
        print_with_color("OK!", "green")
        return count

    ############################################
    # 函数：从QQ好友introduction中提取出Gender, Age, Location, FromLocation, RemarkName等信息
    # @param introduction: QQ好友introduction，如：text: 女 女 | 21岁 | 7月21日 巨蟹座 | 北京大学 | 现居广西 \n南宁 | 来自广西百色 | 学生
    # @intro_dict: 提取出的信息，函数会修改intro_dict
    def extract_friend_info(self, introduction, intro_dict):
        # 从introduction中提取出Gender, Age, Location, FromLocation, RemarkName等信息
        # 如：text: 女 女 | 21岁 | 7月21日 巨蟹座 | 北京大学 | 现居广西 \n南宁 | 来自广西百色 | 学生
        # 提取出：Gender: 女, Age: 21, Location: 北京大学, FromLocation: 广西南宁, RemarkName: 学生
        # 如果提取不到，则不修改intro_dict

        # 提取性别
        gender_match = re.search(r"(\男|女)", introduction)
        if gender_match:
            intro_dict["Gender"] = gender_match.group(1)

        # 提取年龄
        age_match = re.search(r"(\d+)岁", introduction)
        if age_match:
            intro_dict["Age"] = int(age_match.group(1))

        # 提取当前居住地
        location_match = re.search(r"现居(.*?)\|", introduction)
        if location_match:
            intro_dict["Location"] = location_match.group(1).strip()

        # 提取来源地
        from_location_match = re.search(r"来自(.*?)\|", introduction)
        if from_location_match:
            intro_dict["FromLocation"] = from_location_match.group(1).strip()

        # 提取备注名称
        remark_match = re.search(r"个性签名：(.*?)\n", introduction)
        if remark_match:
            intro_dict["RemarkName"] = remark_match.group(1).strip()

        
    ############################################
    # 函数：开始探索QQ好友信息
    def start_exploring(self):
        # 点击查询QQ好友列表
        self.query_qq_friends()
        # 休息1秒等待页面加载完成
        time.sleep(1)
        # 循环获取下一个橱窗的好友信息
        while(True):
            # 获取当前橱窗的好友信息
            count = self.get_current_window_friend_info()
            if count == 0:
                time.sleep(1)
                break

            # 翻动页面(quickly)
            print_with_color(f"翻动页面，继续探索下一个橱窗的好友信息", "yellow")
            width, height = self.controller.get_device_size()
            x, y = width // 2, height // 2
            ret = self.controller.swipe(x, y, "up", "long", True)
            if (ret == "ERROR"):
                print_with_color("ERROR: 翻动页面失败！", "red")
                break
            time.sleep(1)
            
        # 返回页面
        print_with_color("探索完成！", "green")
        self.controller.back()
        time.sleep(1)


# 函数：^C信号处理函数
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
    explore_condition = "女|18-26岁|所在地:广西-南宁-武鸣县"
    qq_friends_explorer = QQFriendsExplorer(device_name, job_dir, explore_condition)
    print_with_color("=======================================================", "yellow")
    print_with_color(f"开始探索QQ好友信息, 查询条件: {explore_condition}", "yellow")
    print_with_color("=======================================================", "yellow")
    # 循环max_try_times次
    max_try_times = 300
    sleep_time = 30
    for i in range(max_try_times):
        if not qq_friends_explorer.init_to_find_qq_friends():
            # 如果初始化失败，则休息一段时间后重试
            time.sleep(sleep_time)
            continue
        time.sleep(5)
        qq_friends_explorer.start_exploring()
        qq_friends_explorer.reset_explored_friends()
        # 如果尝试获取的QQ大多数已经存在数据库中，则退出
        if qq_friends_explorer.get_try_friend_repetitive_count() > max_try_times:
            print_with_color(f"尝试获取的QQ大多数已经存在数据库中，退出", "yellow")
            break
        print_with_color(f"第{i+1}轮探索完成，休息{sleep_time}秒", "yellow")
        time.sleep(sleep_time)
