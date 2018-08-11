import requests, bs4, functools, re, datetime
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class espn_scraper:

    def __init__(self, BASE=datetime.datetime.today(), webdriver='chromedriver.exe'):
        self.XPATHS = {"Scoring": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[1]',
                  "Attacking": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[2]',
                  "Defending": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[3]',
                  "Discipline": '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[4]'}

        self.COLUMN_LABELS = {"Scoring": ['Player', 'T', 'TA', 'CG', 'PG', 'DGC', 'PTS'],
                         "Attacking": ['Player', 'K', 'P', 'R', 'MR', 'CB', 'DB', 'O', 'LWS'],
                         "Defending": ['Player', 'TC', 'T', 'MT', 'LW'],
                         "Discipline": ['Player', 'PC', 'YC', 'RC']}

        self.MATCH_DICT = {"Scoring": 0,
                      "Attacking": 0,
                      "Defending": 0,
                      "Discipline": 0}

        self.BASE = BASE

        self.webdriver = webdriver

    def open_webpage(self, url):
        """
            Takes a url as an input and uses selenium to create a connection to a web page.

            Returns an Selenium WebDriver object for the input web page string.
        """
        print(webdriver)
        browser = webdriver.Chrome(executable_path=self.webdriver)
        browser.get(url)
        return browser

    def generate_urls(self, base, numdays=14):
        """
            This function returns a list of  all the games from today to numdays
            ago and fetches all the links we need to fetch the data.
            Input is an integer number of days to iterate across and a base start date

            Returns a dict of format:

            {'date_1': [url1, url2, url3...], date_2: [...], ..}
        """
        # TODO  Implement a yield method here to yield a single link at a time instead of an entire list?
        date_list = [(base - datetime.timedelta(days=x)).strftime("%Y%m%d") for x in range(0, numdays)]
        urls = ['http://www.espn.co.uk/rugby/fixtures/_/date/' + date for date in date_list]
        links = {}
        for i, url in enumerate(urls):
            soup = bs4.BeautifulSoup(requests.get(url).text, 'lxml')
            date_links = []
            for link in soup.find_all('a'):
                if 'gameId' in str(link.get('href')):
                    date_links.append(re.sub('.*\?', 'http://www.espn.co.uk/rugby/playerstats?', str(link.get('href'))))
            if len(date_links) == 0:
                # No games on this day
                pass
            else:
                links[date_list[i]] = list(set(date_links))
        return links

    @staticmethod
    def log_failed_link(url):
        #Log a failed link
        failed = "matches/failed.txt"
        f = open(failed, 'a')
        f.write(url)
        return f.close()

    @staticmethod
    def get_id(url):
        return re.search('([0-9]+)', url).group(1)

    @staticmethod
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

    def click_away_cookies(self, browser):
        """
           Function to click away the cookie banner so we can access data in the page.
        :param browser: webdriver browser instance
        :return: nothing
        """
        value = '//*[@id="global-viewport"]/div[4]/div/button'
        wait = WebDriverWait(browser, 5)
        wait.until(
            EC.element_to_be_clickable((By.XPATH,
                                        value)))
        element = browser.find_element_by_xpath(value)
        element.click()


    @staticmethod
    def write_commentary(commentary, url):
        """ Write the commentary to a csv, include game id so it can be joined back to main
            data at a later date.  Also includes match url"""
        df = pd.DataFrame(commentary, columns=["commentary"])
        game_id = re.search('([0-9]+)', url).group(1)
        df["game_id"] = game_id
        filename = "matches/commentary{}.csv".format(str(game_id))
        df.to_csv(filename, index=False)

    def get_match_data(self, browser):
        """ This functions gets the match data (i.e. team names, score and competition)
            from an open webapge and returns them."""
        match_data = {}
        html = browser.page_source
        soup = bs4.BeautifulSoup(html, "html.parser")
        match_data["team_a"] = soup.find('div', class_='team team-a').find('span', class_='long-name').get_text()
        match_data["team_a_score"] = soup.find('div', class_='team team-a').find('div',
                                                                                 class_='score icon-font-after').get_text()
        match_data["team_b"] = soup.find('div', class_='team team-b').find('span', class_='long-name').get_text()
        match_data["team_b_score"] = soup.find('div', class_='team team-b').find('div',
                                                                                 class_='score icon-font-before').get_text()
        match_data["competition"] = soup.find('div', class_='game-details header').get_text()
        return match_data

    def get_player_data(self, browser):
        """
            This function has an input of a WebDriver object and returns the player data for a the input webpage

            Return a pandas data frame object
        """

        ## TODO check for timeout here and catch exceptions
        try:
            wait = WebDriverWait(browser, 5)
            wait.until(
                EC.element_to_be_clickable((By.XPATH,
                                            '//*[@id="main-container"]/div/div/div[1]/div[1]/div[1]/ul/li[1]')))
        except Exception as e:
            ## TODO implement timeout catch here, write caught links to a file to try again.
            self.log_failed_link('temp')

        for key, value in self.XPATHS.items():
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
                df = pd.DataFrame(sub_match_list, columns=self.COLUMN_LABELS[key])
                self.MATCH_DICT[key] = df
        frames = []
        for key, value in self.MATCH_DICT.items():
            frames.append(value)
        single_result = functools.reduce(lambda left, right: pd.merge(left, right, on='Player'), frames)
        return single_result

    @staticmethod
    def quit(browser):
        """
            Exit method
        :param browser:
        :return:
        """
        return browser.quit()

    def combine_results(self, match_data, player_data, date, url, venue):
        """ This functions joins the player and match data and returns a single dataframe"""
        player_data["team"] = None
        player_data["team"][0:23] = match_data["team_a"]
        player_data["start_flag"] = None
        player_data["start_flag"][0:15] = 1
        player_data["start_flag"][15:23] = 0
        player_data["start_flag"][23:38] = 1
        player_data["start_flag"][38:] = 0
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

    @staticmethod
    def parse_position(dataframe):
        """ Split player postition and name into two separate columns and return
            a dataframe """
        dataframe["postition"] = dataframe["Player"].str.extract('([A-Z]+$|[N8]+$)')
        dataframe["Player"] = dataframe["Player"].str.replace('([A-Z]+$|[N8]+$)', '')
        return dataframe

    @staticmethod
    def derive_minutes_played(commentary, player_data):
        """ Merge commentary and player data and use to derive minutes played for each
            player """
        commentary = pd.DataFrame(commentary, columns=["commentary"])
        commentary['minute'], commentary['text'] = commentary['commentary'].str.split('\'', 1).str
        commentary = commentary[commentary['text'].str.contains("ubstitute")]
        commentary["Player1"] = commentary["text"].str.extract('-\ (.)')
        commentary["Player2"] = commentary["text"].str.extract('-\ [A-Za-z]+\ (.*)\ ,')
        commentary["Player"] = commentary["Player1"] + ' ' + commentary["Player2"]
        commentary["minutes-played1"] = pd.to_numeric(commentary["minute"][commentary['text'].str.contains("on ")])
        commentary["on flag"] = np.where(commentary['text'].str.contains('on '), 1, 0)
        commentary["minutes-played2"] = pd.to_numeric(commentary["minute"][commentary['text'].str.contains("Player")])
        commentary["minute_from_text"] = commentary["minutes-played1"].fillna(0) + commentary["minutes-played2"].fillna(
            0)
        commentary.drop(['minutes-played1', 'minutes-played2', 'Player1', 'Player2'], axis=1, inplace=True)
        commentary = commentary.iloc[::-1]
        players = player_data["Player"]
        player_data["minutes_played"] = None

        for player in players:
            total = 0
            off_count = 0
            on_count = 0
            last_off = 0
            last_on = 0
            a = player_data["start_flag"][player_data["Player"] == player].iloc[0]

            for index, row in commentary.iterrows():
                if row["Player"] == player and row["on flag"] == 0:
                    last_off = row["minute_from_text"]
                    off_count += 1
                    total += last_off - last_on
                elif row["Player"] == player and row["on flag"] == 1:
                    last_on = row["minute_from_text"]
                    on_count = on_count + 1
                else:
                    pass
            if off_count == 0 and a == 1:
                total = 80
            elif on_count == 0 and a == 0:
                total = 0
            elif on_count == 1 and a == 0:
                total = 80 - last_on
            else:
                pass

            player_data["minutes_played"][player_data["Player"] == player] = total
        return player_data

    def ingest(self):
        """
            Main method to run pipeline
        :return:
        """
        # TODO replace main method here
        pass

    @staticmethod
    def commit_results(final_results):
        """
            Write out results
        :return:
        """
        filename = "matches/match{}.csv".format(str(game_id))
        final_results.to_csv(filename, index=False)

if __name__ == '__main__':
    wrapper = espn_scraper(BASE=datetime.datetime.today())
    urls = wrapper.generate_urls(base=wrapper.BASE, numdays=5)
    print(urls)
    urls = {21071111: ["http://www.espn.co.uk/rugby/playerstats?gameId=291271&league=289234"]}
    for date, url_list in urls.items():
        for url in url_list:
            try:
                game_id = wrapper.get_id(url)
                venue, commentary = wrapper.get_match_commentary(url)
                wrapper.write_commentary(commentary, url)
                browser = wrapper.open_webpage(url)
                match_data = wrapper.get_match_data(browser)
                wrapper.click_away_cookies(browser)
                player_data = wrapper.get_player_data(browser)
                results = wrapper.combine_results(match_data, player_data, date, url, venue)
                wrapper.quit(browser)
                final_parsed = wrapper.parse_position(results)
                final_results = wrapper.derive_minutes_played(commentary, final_parsed)
                wrapper.commit_results(final_results)
                print(final_results)
            except:
                wrapper.log_failed_link(url)
                wrapper.quit(browser)

