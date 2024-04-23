from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = Flask(__name__)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Missing required parameter: 'query'"}), 400

    base_url = "https://estherox123.github.io/html_parser/"
    index_page = requests.get(base_url)
    if index_page.status_code != 200:
        return jsonify({"error": "Failed to load index page"}), 500
    soup = BeautifulSoup(index_page.content, 'html.parser')

    links = [a['href'] for a in soup.find_all('a', href=True)]

    search_results = []

    for link in links:
        full_url = urljoin(base_url, link)
        html_page = requests.get(full_url)
        if html_page.status_code == 200:
            page_soup = BeautifulSoup(html_page.content, 'html.parser')
            page_text = page_soup.get_text().lower()
            page_title = page_soup.find('h1').get_text() if page_soup.find('h1') else "No Title"
            page_company = page_soup.find('h3').get_text() if page_soup.find('h3') else "No Company"
            page_date = page_soup.find('h2').get_text() if page_soup.find('h2') else "No Date"
            
            if query.lower() in page_text:
                start = page_text.find(query.lower())
                sentence_start = page_text.rfind('.', 0, start) + 2 if page_text.rfind('.', 0, start) != -1 else 0
                end = start + len(query) + 750
                snippet = page_text[sentence_start:end].replace('\n', ' ').strip()
                search_results.append({"title": f"{page_company} - {page_title}", "date": page_date, "link": full_url, "snippet": snippet})
        else:
            print(f"Failed to load page: {full_url}")

            
            end = start + len(query) + 750  # Adjust the range as needed
            snippet = page_text[sentence_start:end].replace('\n', ' ').strip()
            search_results.append({"title": page_company + " - " + page_title, "date": page_date, "link": base_url + link, "snippet": snippet})


    return jsonify(search_results)

if __name__ == '__main__':
    app.run(debug=True)
