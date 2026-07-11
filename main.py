import requests
import json

def main():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get("https://www.newgrad-jobs.com/", headers=headers)
    html = response.text
    print(html)



if __name__ == "__main__":
    main()
