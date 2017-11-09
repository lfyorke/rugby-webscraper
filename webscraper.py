import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import bs4
import functools
import re
import datetime


def generate_urls(numdays):
    """ This function returns a list of  all the games from today to numdays
    ago and fetches all the links we need to fetch the data."""
    base = datetime.datetime.today()
    date_list = [(base - datetime.timedelta(days=x)).strftime("%Y%m%d")
                 for x in range(0, numdays)]
    base_url = 'http://www.espn.co.uk/rugby/fixtures/_/date/'
    urls = [base_url + date for date in date_list]
    links = []
    for url in urls:
        soup = bs4.BeautifulSoup(requests.get(url).text, 'lxml')
        for link in soup.find_all('a'):
            if 'gameId' in str(link.get('href')):
                links.append(re.sub('.*\?',
                                    'http://www.espn.co.uk/rugby/playerstats?',
                                    str(link.get('href'))))
    return (list(set(links)))


xpaths = {"Scoring": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[1]',
          "Attacking": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[2]',
          "Defending": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[3]',
          "Discipline": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[4]'}

columns_labels = {"Scoring": ['Player', 'T', 'TA', 'CG', 'PG', 'DGC', 'PTS'],
                  "Attacking": ['Player', 'K', 'P', 'R', 'MR', 'CB', 'DB', 'O', 'LWS'],
                  "Defending": ['Player', 'TC', 'T', 'MT', 'LW'],
                  "Discipline": ['Player', 'PC', 'YC', 'RC']}

no_columns = {"Scoring": 7,
              "Attacking": 9,
              "Defending": 5,
              "Discipline": 4}

match_data = {"Scoring": 0,
              "Attacking": 0,
              "Defending": 0,
              "Discipline": 0}


def scrape_urls(url_list):
    """ This function iterates over a list of urls and returns a dataframe of
    results """
    all_results = []
    for url in url_list:
        try:
            path_to_driver = "C:\\Users\\leo.yorke\\Desktop\\Leo\espn\\chromedriver\\chromedriver.exe"
            browser = webdriver.Chrome(executable_path=path_to_driver)
            browser.get(url)
            wait = WebDriverWait(browser, 5)
            element = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[1]')))

            for key, value in xpaths.items():
                skip = 0
                try:
                    element = browser.find_element_by_xpath(value)
                    element.click()
                    html = browser.page_source
                    soup = bs4.BeautifulSoup(html, "html.parser")
                    for data in soup.find_all('div', class_='col-b'):
                        sub_match_list = []
                        for tables in data.find_all("tbody"):
                            for row in tables.find_all("tr"):
                                player_row = []
                                for element in row:
                                    player_row.append(element.get_text())
                                sub_match_list.append(player_row)
                        df = pd.DataFrame(sub_match_list, columns=columns_labels[key])
                        match_data[key] = df
                except Exception:
                    skip = 1
                    pass
            browser.quit()
            if skip == 0:
                frames = []
                for key, value in match_data.items():
                    frames.append(value)
                single_result = functools.reduce(lambda left,right: pd.merge(left,right,on='Player'), frames)
                all_results.append(single_result)
            else:
                pass
        except Exception:
            pass
    return pd.concat(all_results)


def write_results(result_set):
    """ This function writes a dataframe to a csv"""
    return result_set.to_csv("C:\\Users\\leo.yorke\\Desktop\\Leo\espn\\match.csv", index=False)

urls = generate_urls(5)
print(urls)
results = scrape_urls(urls)
write_results(results)
results.to_csv("match.csv", index=False)
