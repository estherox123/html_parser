import requests
from bs4 import BeautifulSoup
import urllib
from urllib.parse import urljoin
import os
import PyPDF2
import re
import subprocess
import sys


def push_changes_to_github(application_path, git_executable, commit_message="Update content"):
    try:
        # Define HOME environment variable for SSH
        os.environ['HOME'] = os.path.expanduser('~')
        
        # Set the GIT_SSH_COMMAND to use the custom deploy key and PortableGit ssh
        ssh_executable = os.path.join(application_path, 'PortableGit', 'usr', 'bin', 'ssh.exe')
        ssh_key_path = os.path.join(application_path, 'new_deploy_key')
        os.environ['GIT_SSH_COMMAND'] = f'"{ssh_executable}" -i "{ssh_key_path}" -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no'
        
                
        # Set repository path
        repository_path = os.path.join(application_path)
        os.chdir(repository_path)
        
        # Stash any unstaged changes
        subprocess.run([git_executable, "stash", "--include-untracked"], check=True)
        print("Stashed any unstaged changes.")

        # Pull the latest changes from the remote repository with rebase to reduce merge conflicts
        subprocess.run([git_executable, "pull", "--rebase", "origin", "main"], check=True)
        print("Pulled latest changes from main.")

        # Reapply stashed changes if any
        subprocess.run([git_executable, "stash", "pop"], check=False)  # This may raise an error if there are conflicts
        
        # Check for conflicts after unstashing
        status_output = subprocess.run([git_executable, "status", "--porcelain"], text=True, stdout=subprocess.PIPE).stdout
        if "UU" in status_output:
            print("There are merge conflicts after unstashing. Please resolve them before proceeding.")
            return  # Exit the function, as manual intervention is required

        # Add all changes including new files
        subprocess.run([git_executable, "add", "."], check=True)
        print("Added all changes.")

        # Commit the changes
        if status_output.strip():
            subprocess.run([git_executable, "commit", "-m", commit_message], check=True)
            print(f"Committed changes with message: '{commit_message}'")

            # Push the changes
            subprocess.run([git_executable, "push", "origin", "main"], check=True)
            print("Changes pushed to GitHub successfully.")
        else:
            print("No changes to commit.")

    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")


def get_all_html_folders(repo_url):
    api_url = f"https://api.github.com/repos/{repo_url}/contents/"
    response = requests.get(api_url)
    response.raise_for_status()
    content_list = response.json()
    html_folders = [content['name'] for content in content_list if content['type'] == 'dir' and content['name'].endswith('_HTML')]
    return html_folders


def update_navigation_page(repo_url, output_folder):
    # Fetch all HTML folders
    html_folders = get_all_html_folders(repo_url)
    # Initialize a dictionary to map filenames to their paths
    file_path_dict = {}

    # Iterate over each folder and fetch HTML files within them
    for folder_name in html_folders:
        folder_contents_url = f"https://api.github.com/repos/{repo_url}/contents/{folder_name}"
        response = requests.get(folder_contents_url)
        response.raise_for_status()
        folder_contents = response.json()
        # For each HTML file, add its path to the dictionary
        for content in folder_contents:
            if content['name'].endswith('.html'):
                # The path will be the folder name plus the file name
                file_path_dict[content['name']] = f"{folder_name}/{content['name']}"

    # Now write the index file with the correct paths
    with open(os.path.join(output_folder, 'index.html'), 'w', encoding='utf-8') as index_file:
        index_file.write("<!DOCTYPE html>\n<html lang='en'>\n<head>\n    <meta charset='UTF-8'>\n")
        index_file.write("    <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n")
        index_file.write("    <title>Analysis Reports</title>\n</head>\n<body>\n    <h1>Analysis Reports</h1>\n")
        index_file.write("    <ul>\n")
        for file_name, file_path in file_path_dict.items():
            # Write the list item with a relative path to the HTML file
            index_file.write(f"        <li><a href='./{file_path}'>{file_name}</a></li>\n")
        index_file.write("    </ul>\n</body>\n</html>")


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

    print(f"Markdown file created: {file_path}")


def create_html_dir(base_folder_path):
    html_folder_path = f"{base_folder_path}_html"

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

def code():
        # Determine if the application is a frozen executable (i.e., compiled with PyInstaller)
    if getattr(sys, 'frozen', False):
        # The application is running as a standalone executable
        application_path = os.path.dirname(sys.executable)
    else:
        # The application is running as a normal Python script
        application_path = os.path.dirname(os.path.abspath(__file__))

    # Use application_path to construct paths relative to the executable's location
    git_executable = os.path.join(application_path, 'PortableGit', 'bin', 'git.exe')

    # Define a temporary directory for operations
    tmp_dir = os.path.join(application_path, 'tmp')
    os.makedirs(tmp_dir, exist_ok=True)
    os.environ['TMP'] = tmp_dir

    # Set up the SSH configuration for Git
    config_content = f"""Host github.com
    User git
    IdentityFile {application_path}\\new_deploy_key
    IdentitiesOnly yes
    """
    # Write the content to config.txt
    with open('config.txt', 'w') as config_file:
        config_file.write(config_content)

    # Initial Git setup: add, commit, and push any pre-existing changes
    push_changes_to_github(commit_message="Initial setup")

    # Input the Korean text
    keyword = input("검색어를 입력해주세요: ")

    # Get the URL
    url = create_search_url(keyword)

    # Create a new directory with the keyword
    current_dir = os.getcwd()
    folder_path = create_unique_dir(current_dir, keyword)

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
                    html_folder_base_path = os.path.join(application_path, f"{keyword}_HTML")

                    # Ensure the HTML directory exists
                    if not os.path.exists(html_folder_base_path):
                        os.makedirs(html_folder_base_path)

                    # Construct the HTML file path
                    html_file_path = os.path.join(html_folder_base_path, f"{file_name} - {date}.html")
                    
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

                    print(f"HTML file created: {html_file_path}")

                    #Add the HTML file path to the list
                    html_files.append(html_file_path)

            else:
                print("종목명과 제목을 찾지 못했습니다.")
        else:
            print("해당 PDF를 찾지 못했습니다.")

    print(f"모든 파일이 {keyword} 폴더에 다운로드 되었습니다.")

    
    repo_url = "estherox123/html_parser"
    output_folder = application_path # This should be the path where your index.html is located

    # Commit and push changes to GitHub
    push_changes_to_github("Add new analysis reports and updated index")

    # Call the function with the appropriate folder name
    update_navigation_page(repo_url, output_folder)

    # Commit and push changes to GitHub
    push_changes_to_github("Add new analysis reports and updated index")

    pass

if __name__ == "__main__":
    code()