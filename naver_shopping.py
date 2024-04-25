import re
import os
import requests
import pandas as pd
import PySimpleGUI as sg

# 네이버 쇼핑 API 설정
client_id = "JBRYdiQSa7QH3EK7oKWN"
client_secret = "6DDVgFiUxe"

url = "https://openapi.naver.com/v1/search/shop.json"
headers = {
    "X-Naver-Client-Id": client_id,
    "X-Naver-Client-Secret": client_secret
}

def clean_text(text):
    cleaned_text = re.sub(r"<b>", "", text)
    cleaned_text = re.sub(r"</b>", "", cleaned_text)
    return cleaned_text

def extract_quantity(title):
    # Regular expression to find bulk quantity (e.g., 10개, 20-pack)
    match = re.search(r"(\d+)\s*(개|회|매|통|pack|box|set)", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 1  # Assume it's a single item if no bulk information is found

def get_shopping_results(query, display):
    params = {
        "query": query,
        "display": display
    }

    # API 요청 보내기
    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    # 검색 결과 확인
    if "items" in data:
        items = data["items"]
        result_list = []

        for item in items:
            title = clean_text(item["title"])
            price = int(item["lprice"])  # Ensure price is an integer for calculation
            quantity = extract_quantity(title)
            unit_price = price // quantity  # Calculate unit price
            brand = item.get("brand", "")
            category = item.get("category", "")
            link = item["link"]
            result_list.append({
                "브랜드": brand,
                "상품명": title,
                "카테고리": category,
                "가격": price,
                "개당 가격": unit_price,
                "링크": link,
            })

        # DataFrame 생성
        df = pd.DataFrame(result_list)

        # 결과를 엑셀 파일에 저장
        file_name = f"naver_shopping {query}.xlsx"
        counter = 0
        while os.path.exists(file_name):
            counter += 1
            file_name = f"naver_shopping {query}_{counter}.xlsx"
        df.to_excel(file_name, index=False)
        print(f"{len(result_list)}개의 결과를 {file_name}에 저장했습니다.")
    else:
        print("검색 결과가 없습니다.")


# Define the layout of the window
layout = [
    [sg.Text("제품명을 입력해주세요:")],
    [sg.Input(key='-KEYWORD-')],
    [sg.Text("출력할 개수를 입력하세요:")],
    [sg.Input(key='-DISPLAY-')],
    [sg.Button('검색'), sg.Exit()],
    [sg.Text('', key='-STATUS-')],
]

# Create the window
window = sg.Window('네이버 쇼핑 제품 가격 비교', layout, return_keyboard_events=True)

while True:  # Event Loop
    event, values = window.read()

    if event == sg.WIN_CLOSED or event == 'Exit':
        break
    elif event in ('검색', '\r', '\n'):
        keyword = values['-KEYWORD-']  # Get the entered keyword
        display = values['-DISPLAY-']  # Get the entered display number
        window['-STATUS-'].update(value='검색중입니다...')
        window.refresh()
        # Here you call get_shopping_results and pass the inputs from the user
        get_shopping_results(keyword, int(display))  # Ensure display is an integer

        # After processing is done, you can update the status
        window['-STATUS-'].update(value='완료되었습니다.')
        sg.popup('다운로드가 완료되었습니다.', title="다운로드 완료")  # "Download is complete."

        # Reset the input field for new input
        window['-KEYWORD-'].update(value='')
        window['-DISPLAY-'].update(value='')

# Close the window when done
window.close()