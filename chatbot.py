import gradio as gr
import os
import requests
import json
import random
import pdfplumber
from cnocr import CnOcr
import magic
import re

url = "http://3.8.48.225:3001/api/v1/chat/completions"
# 数据处理应用
key1 = "fastgpt-vUAjlaYgC8i01SY96dPFHKU5gC5eOyfJYWUK354jhIKp7VryAnvFCeawe"
# 数据标注应用
key2 = "fastgpt-x9jWXE7GSonLdmG1sbTYr5Ck9RKrwFskB0SCg84fA08G4K4BfK5Hy"


def clear_content():
    return [], "", None, "", "", None


# 对话数据处理
def data_processed(key, chatId, variables, input_text):
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }
    payload = {
        "chatId": chatId,
        "stream": False,
        "detail": False,
        "variables": variables,
        "messages": [
            {
                "content": input_text,
                "role": "user"
            }
        ]
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.ok:
        json_data = response.json()
        output = json_data["choices"][0]["message"]["content"]
    else:
        # 如果有错误，打印错误详情
        output = "Error occurred:\n" + str(response.status_code) + "\n" + response.text
    return output


def file_processed(file_input):
    return file_input


def extract_json(variables):
    json_string_match = re.search(r'\{.*\}', variables)
    if json_string_match:
        json_string = json_string_match.group()
        try:
            # 替换单引号为双引号以形成有效的JSON格式
            json_string = json_string.replace("'", '"').replace('\\', '')
            data = json.loads(json_string)
        except:
            data = None
    else:
        data = None
        # print("在文本中没有找到JSON字符串")
    return data


def example_processed(stats, variables, file_input):
    # 文件文本提取
    if file_input is not None:
        file_path = file_input.name
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(file_path)
        if 'image' in file_type:
            ocr = CnOcr()  # 所有参数都使用默认值
            out = ocr.ocr(file_input)
            context = ""
            for line in out:
                context = context + line['text'] + '\n'
            file_content = ["jpg", file_path, [context], context]
        elif 'pdf' in file_type:
            context = []
            with pdfplumber.open(file_input) as pdf:
                for page in pdf.pages:
                    context.append(page.extract_text())
            file_content = ["pdf", file_path, context, context[0][:512]]
    # 样例显示
    vars = extract_json(variables)
    if vars is not None:
        var1 = {
            'description': vars['description'],
            'contain qa data': vars['contain qa data']
        }
        var2 = {
            'label enable': vars['label enable'],
            'label content': vars['label content']
        }
        random_uid = str(random.randint(0, 999999)).zfill(6)
        stats = [var1, var2, file_content, random_uid]  # 数据处理与数据标注的参量
        # 数据处理
        output1 = data_processed(key1, random_uid, var1, file_content[-1]).strip()
        # 数据标注
        output2 = data_processed(key2, random_uid, var2, file_content[-1]).strip()
        chat_output = [[None, None], [None, output1 + '\n###\n' + output2]]
    else:
        output = "Error, the data handling configuration is incorrect !"
        chat_output = [[None, None], [None, output]]
    return stats, variables, chat_output


def require_change(stats, chat_input, history):
    # 在本次demo中，数据自动标注只取第一次标注结果，暂不做改动
    autolabel = history[1][1].split('\n###\n')[-1]
    var1 = stats[0]
    chatId = stats[-1]
    output = data_processed(key1, chatId, var1, chat_input).strip()
    # 用户的输入作为一条消息
    user_msg = [chat_input, None]
    # Bot的响应作为一条消息
    bot_response = [None, output + '\n###\n' + autolabel]
    history.append(user_msg)
    history.append(bot_response)
    return "", history


def all_file_processed(stats, history):
    file_type = stats[2][0]
    file_name = stats[2][1]
    file_context = stats[2][2]
    file_example = stats[2][3]
    example = history[-1][1]
    autolabel = history[1][1].split('\n###\n')[-1]
    var1 = stats[0]
    var1['example'] = file_example + '\n\n' + example
    var2 = stats[1]
    chatId = stats[-1]
    download_file_path = str(file_name) + ".txt"
    if file_type == 'jpg':
        with open(download_file_path, 'a', encoding='utf-8') as file:
            file.write(example + '\n')
            file.write(autolabel + '\n\n')
    elif file_type == 'pdf':
        for content in file_context:
            # 数据处理
            output1 = data_processed(key1, chatId, var1, content).strip()
            # 数据标注
            output2 = data_processed(key2, chatId, var2, content).strip()
            with open(download_file_path, 'a', encoding='utf-8') as file:
                file.write(output1 + '\n')
                file.write(output2 + '\n\n')

    if os.path.exists(download_file_path):
        return download_file_path
    else:
        # 如果文件不存在，返回 None 或者可以返回错误信息
        return None


if __name__ == '__main__':
    with gr.Blocks() as demo:
        # 文字 Logo
        gr.Markdown(
            """
            # Fucol Data Handling AI
            Welcome to the data handling AI developed by Fucol, please fill in the configuration information and upload the file
            """
        )
        stats = gr.State([])
        with gr.Row():
            variables = gr.Textbox(label="Data Handling Requirements",
                                   placeholder="Please fill in the data handling configuration")
            file_input = gr.File(label="upload the file")
        with gr.Row():
            submit = gr.Button("Submit")
            clear_button = gr.Button("Clear")
        with gr.Row():
            chat_output = gr.Chatbot()
        with gr.Row():
            chat_input = gr.Textbox(placeholder="enter your improvement command about the data sample...")
            download_btn = gr.Button("Start data handling")
        # 文件下载输出组件
        file_download = gr.File(label="Download File")

        '''
        功能流程：
        1.客户填入需求配置，上传文件后，点击submit提交，得到参量与文件文本——涉及函数：参量提取、文件文本识别
        2.将识别的文本与参量送入数据处理与数据标注应用，获得输出
        3.客户不满意输出，在窗口中添加诉求
        4.完成诉求后，取最后一次对话的数据处理结果作为数据样例，点击开始数据处理，完毕后提供下载
        '''
        # 当文件上传时，触发file_processed函数
        file_input.change(
            file_processed,
            inputs=file_input,
            outputs=file_input
        )
        submit.click(
            example_processed,
            inputs=[stats, variables, file_input],
            outputs=[stats, variables, chat_output]
        )
        clear_button.click(
            clear_content,
            outputs=[stats, variables, file_input, chat_input, chat_output, file_download]
        )

        chat_input.submit(
            require_change,
            inputs=[stats, chat_input, chat_output],
            outputs=[chat_input, chat_output]
        )

        download_btn.click(all_file_processed, [stats, chat_output], file_download)

    demo.launch(server_port=3008, server_name="127.0.0.1")
