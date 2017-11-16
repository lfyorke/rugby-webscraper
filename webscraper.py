import requests, bs4, functools, re, datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

XPATHS = {"Scoring": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[1]',
          "Attacking": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[2]',
          "Defending": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[3]',
          "Discipline": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[4]'}

COLUMN_LABELS = {"Scoring": ['Player', 'T', 'TA', 'CG', 'PG', 'DGC', 'PTS'],
                  "Attacking": ['Player', 'K', 'P', 'R', 'MR', 'CB', 'DB', 'O', 'LWS'],
                  "Defending": ['Player', 'TC', 'T', 'MT', 'LW'],
                  "Discipline": ['Player', 'PC', 'YC', 'RC']}

MATCH_DICT = {"Scoring": 0,
              "Attacking": 0,
              "Defending": 0,
              "Discipline": 0}

def generate_urls(numdays):
    """ This function returns a list of  all the games from today to numdays
    ago and fetches all the links we need to fetch the data."""
    base = datetime.datetime.today()
    date_list = [(base - datetime.timedelta(days=x)).strftime("%Y%m%d")
                 for x in range(0, numdays)]
    base_url = 'http://www.espn.co.uk/rugby/fixtures/_/date/'
    urls = [base_url + date for date in date_list]
    links = {}
    for i, url in enumerate(urls):
        soup = bs4.BeautifulSoup(requests.get(url).text, 'lxml')
        date_links = []
        for link in soup.find_all('a'):
            if 'gameId' in str(link.get('href')):
                date_links.append(re.sub('.*\?', 'http://www.espn.co.uk/rugby/playerstats?', str(link.get('href'))))
        links[date_list[i]] = list(set(date_links))
    return links


def open_webpage(url):
    """ This function opens a url with webdriver and returns it."""
    browser = webdriver.Chrome(executable_path="chromedriver.exe")
    browser.get(url)
    return browser


def get_match_data(browser):
    """ This functions gets the match data (i.e. team names, score and competition) 
        from an open webapge and returns them."""
    match_data = {}
    html = browser.page_source
    soup = bs4.BeautifulSoup(html, "html.parser")
    match_data["team_a"] = soup.find('div', class_='team team-a').find('span', class_='long-name').get_text()
    match_data["team_a_score"] = soup.find('div', class_='team team-a').find('div', class_='score icon-font-after').get_text()
    match_data["team_b"] = soup.find('div', class_='team team-b').find('span', class_='long-name').get_text()
    match_data["team_b_score"] = soup.find('div', class_='team team-b').find('div', class_='score icon-font-before').get_text()
    match_data["competition"] = soup.find('div', class_='game-details header').get_text()    
    return match_data


def get_player_data(browser):
    """ This function returns the indivual players data from the open webpage and 
        returns it."""
    wait = WebDriverWait(browser, 5)
    element = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[1]')))
    for key, value in XPATHS.items():
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
            df = pd.DataFrame(sub_match_list, columns=COLUMN_LABELS[key])
            MATCH_DICT[key] = df
    frames = []
    for key, value in MATCH_DICT.items():
        frames.append(value)
    single_result = functools.reduce(lambda left,right: pd.merge(left,right,on='Player'), frames)
    return single_result

def combine_results(match_data, player_data, date, url, venue):
    """ This functions joins the player and match data and returns a single dataframe"""
    player_data["team"] = None
    player_data["team"][0:23] = match_data["team_a"]
    player_data["team"][23:] = match_data["team_b"]
    player_data["score"] = None
    player_data["score"][0:23] = match_data["team_a_score"]
    player_data["score"][23:] = match_data["team_b_score"]
    player_data["competition"] = match_data["competition"]
    player_data["date"] = date
    player_data["url"] = url
    player_data["game_id"] = re.search('([0-9]+)', url).group(1)
    player_data["venue"] = venue
    return player_data


def write_results(all_data):
    """ This function writes a dataframe to a csv"""
    return all_data.to_csv("match.csv", index=False)


def parse_position(dataframe):
    """ Split player postition and name into two separate columns and return
        a dataframe """
    dataframe["postition"] = dataframe["Player"].str.extract('([A-Z]+$|[N8]+$)')
    dataframe["Player"] = dataframe["Player"].str.replace('([A-Z]+$|[N8]+$)', '')
    return dataframe


def get_match_commentary(url):
    """ Return the match commentary which will be used to get minutes played for each player 
        and also used to get the position of replacements"""
    url_updated = re.sub("playerstats", "commentary", url)
    webpage = requests.get(url_updated)
    soup = bs4.BeautifulSoup(webpage.text, "html.parser")
    venue = re.search(": (.*)", soup.find("div", class_="capacity").get_text()).group(1)
    col = soup.find("div", class_="col-two")
    commentary = []
    for row in col.find_all("tr"):
        commentary.append(row.get_text())
    return venue, commentary


def write_commentary(commentary, url):
    """ Write the commentary to a csv, include game id so it can be joined back to main
        data at a later date.  Also includes match url"""
    df = pd.DataFrame(commentary, columns=["commentary"])
    game_id = re.search('([0-9]+)', url).group(1)
    df["game_id"] = game_id
    filename = "matches/commentary{}.csv".format(str(game_id))
    df.to_csv(filename, index=False)


if __name__ == "__main__": 
    urls = generate_urls(5)
    counter = 0
    for date, url_list in urls.items():
        for url in url_list:
            try:
                venue, commentary = get_match_commentary(url)
                write_commentary(commentary, url)
                browser = open_webpage(url)
                match_data = get_match_data(browser)
                player_data = get_player_data(browser)
                results = combine_results(match_data, player_data, date, url, venue)
                browser.quit()
                counter += 1
                final_parsed = parse_position(results)
                filename = "matches/match{}.csv".format(str(counter))
                final_parsed.to_csv(filename, index=False)   
            except:
                failed = "matches/failed{}.txt".format(str(counter))
                f = open(failed,'w')
                f.write(url)
                f.close()
                browser.quit()
                

