import requests
from bs4 import BeautifulSoup
import urllib
from urllib.parse import urljoin
import os
import PyPDF2
import re
import subprocess
import sys
import PySimpleGUI as sg
import threading


def save_text_as_markdown(stock_name, title, date, content, output_folder):
    # Sanitize the filename
    file_name = f"{stock_name} - {title} - {date}.md".replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '').strip()
    file_path = os.path.join(output_folder, file_name)

    # Markdown content with front matter
    markdown_content = f"""---
title: "{title}"
date: {date}
stock_name: "{stock_name}"
---

{content}
"""

    # Write the Markdown content to a file
    with open(file_path, 'w', encoding='utf-8') as md_file:
        md_file.write(markdown_content)

    ##print(f"Markdown file created: {file_path}")


def create_html_dir(base_folder_path):
    html_folder_path = f"{base_folder_path}"

    if not os.path.exists(html_folder_path):
        os.makedirs(html_folder_path)

    return html_folder_path


def clean_extracted_text(text):
    # Remove special characters like "\uf075", "\n", etc.
    text = text.replace('\\n', ' ')  # Newlines
    text = text.replace('\n', ' ')   # Newlines that might not have been caught by the regex
    text = re.sub(r'\\uf[0-9a-f]{3}', '', text)  # Unicode artifacts
    
    # Additional common artifacts you might want to clean
    text = text.replace('\\u201c', '"').replace('\\u201d', '"')  # Smart quotes
    text = text.replace('\\u2018', "'").replace('\\u2019', "'")  # Smart single quotes
    
    return text


def create_search_url(keyword):
    # Encode the Korean text into URL encoding
    encoded_keyword = urllib.parse.quote(keyword.encode('euc-kr'))
    
    # Insert the encoded keyword into the URL
    url = f"https://finance.naver.com/research/company_list.naver?searchType=keyword&keyword={encoded_keyword}&brokerCode=&writeFromDate=&writeToDate=&itemName=&itemCode=&x=0&y=0"
    
    return url


def create_unique_dir(base_path, keyword):
    # Replace characters not allowed in directory names and remove spaces
    safe_keyword = keyword.replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '').replace(' ', '_')
    folder_path = os.path.join(base_path, safe_keyword)
    counter = 1
    
    # If the directory exists, append a number until it is unique
    while os.path.exists(folder_path):
        folder_path = os.path.join(base_path, f"{safe_keyword}_{counter}")
        counter += 1
    
    # Create the directory
    os.makedirs(folder_path)
    return folder_path

def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text() + ' '
        return text.strip()
    except Exception as e:
        print(f"An error occurred while processing {pdf_path}: {e}")
        return ''


def find_html_files(directory):
    html_files = [f for f in os.listdir(directory) if f.endswith('.html')]
    return html_files


def code(keyword):
    # Determine if the application is a frozen executable (i.e., compiled with PyInstaller)
    if getattr(sys, 'frozen', False):
        # The application is running as a standalone executable
        application_path = os.path.dirname(sys.executable)
    else:
        # The application is running as a normal Python script
        application_path = os.path.dirname(os.path.abspath(__file__))


    # Get the URL
    url = create_search_url(keyword)

    # Create a new directory with the keyword
    downloaded_files_path = os.path.join(application_path, 'downloaded_files')
    folder_path = create_unique_dir(downloaded_files_path, keyword)

    # Perform a GET request to fetch the raw HTML content
    response = requests.get(url)
    webpage = response.content

    # Create a BeautifulSoup object and specify the parser
    soup = BeautifulSoup(webpage, 'html.parser')

    # Find all the table rows on the webpage
    rows = soup.find_all('tr')

    # A list to hold all the paths to the HTML files for navigation updating
    html_files = []

    for row in rows:
        # Find all 'a' tags, then filter for those with '.pdf' links
        a_tags = row.find_all('a', href=True)
        pdf_link_tag = next((a for a in a_tags if a['href'].endswith('.pdf')), None)

        if pdf_link_tag:
            pdf_link = pdf_link_tag['href']
            
            # Extract '종목명' and '제목' from the row
            종목명_tag = row.find('a', {'title': True})
            제목_tag = row.find('td', class_='file').find_previous_sibling('td').find_previous_sibling('td')
            날짜_tag = row.find('td', class_='date')

            if 종목명_tag and 제목_tag:
                stock_name = 종목명_tag.get('title').strip()
                title = 제목_tag.text.strip()
                date = 날짜_tag.text.strip()
                
                # Construct the meaningful file name
                file_name = f"{stock_name} - {title}.pdf"
                
                # Make the file name file-system safe
                file_name = file_name.replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '').strip()
                
                # Check if the link is absolute or relative
                if not pdf_link.startswith('http'):
                    pdf_link = urllib.parse.urljoin('https://ssl.pstatic.net/imgstock/upload/research/company/', pdf_link)
                
                print(f"{file_name} 다운로드 중.")
                pdf_response = requests.get(pdf_link)
                
                # Create the full path for the file
                file_path = os.path.join(folder_path, file_name)

                # Write the PDF content to a file
                with open(file_path, 'wb') as file:
                    file.write(pdf_response.content)
                    content = extract_text_from_pdf(file_path)  # Extract text from the downloaded PDF
                    content = clean_extracted_text(content)
                    
                    
                    # Create a directory for HTML files
                    html_folder_base_path = create_html_dir(os.path.join(downloaded_files_path, f"{keyword}_HTML"))

                    # Construct the HTML file path
                    html_file_path = os.path.join(html_folder_base_path, f"{stock_name} - {title} - {date}.html")
                    
                    # Simple HTML structure for your content
                    html_content = f"""<html>
    <head>
        <title>{title}</title>
    </head>
    <body>
        <h1>{title}</h1>
        <h2>{date}</h2>
        <h3>{stock_name}</h3>
        <p>{content}</p>
    </body>
    </html>"""

                    # Write the HTML content to a file
                    with open(html_file_path, 'w', encoding='utf-8') as html_file:
                        html_file.write(html_content)

                    ##print(f"HTML file created: {html_file_path}")

                    #Add the HTML file path to the list
                    html_files.append(html_file_path)

            else:
                print("종목명과 제목을 찾지 못했습니다.")
        else:
            print("해당 PDF를 찾지 못했습니다.")

    print(f"모든 파일이 {keyword} 폴더에 다운로드 되었습니다.")

    



# Define the layout of the window
layout = [
    [sg.Text("검색어를 입력해주세요:")],
    [sg.Input(key='-KEYWORD-')],
    [sg.Button('검색'), sg.Exit()],
    [sg.Text('', key='-STATUS-')],
]

# Create the window
window = sg.Window('분석 리포트 다운로드', layout, return_keyboard_events=True)

while True:  # Event Loop
    event, values = window.read()

    if event == sg.WIN_CLOSED or event == 'Exit':
        break
    elif event in ('검색', '\r', '\n'):
        keyword = values['-KEYWORD-']  # Get the entered keyword
        window['-STATUS-'].update(value='다운로드 중입니다...')
        window.refresh()
        code(keyword)

        # After processing is done, you can update the status
        window['-STATUS-'].update(value='완료되었습니다.')

        sg.popup('다운로드가 완료되었습니다.', title="다운로드 완료")  # "Download is complete."

        # Reset the input field for new input
        window['-KEYWORD-'].update(value='')

# Close the window when done
window.close()

