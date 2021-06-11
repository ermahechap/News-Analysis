from tinydb import TinyDB, Query, where
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm, trange
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import os.path
import datetime
import time
import re

def selenium_opt():
    options = Options()
    options.add_argument("--incognito")
    options.add_argument("--start-maximized")
    #options.add_argument("--headless")
    return options

class NewsSource:
    def __init__(
        self,
        url,
        options=selenium_opt(),
        consecutive_crawls=10, #urls
        base_sleep_time=20, #seconds
        sleep_increase_ratio=1.5, #percentaje
        dbs_path = './'
    ):
        self.url = url
        options = options
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(url)
        self.db_urls = TinyDB(os.path.join(dbs_path, 'urls.json'))
        self.db_crawled = TinyDB(os.path.join(dbs_path, 'crawled.json'))

        self.consecutive_crawls = consecutive_crawls
        self.base_sleep_time = base_sleep_time #seconds
        self.sleep_increase_ratio = sleep_increase_ratio

    def get_n_pages(self):
        raise NotImplementedError

    def get_article_url(self, element):
        raise NotImplementedError

    def get_articles(self):
        raise NotImplementedError

    def scrape_article(self, db_urls_id):
        raise NotImplementedError

    def store_url(self, info):
        Article = Query()
        if self.db_urls.search(Article.url == info['url']):
            return False
        self.db_urls.insert(info)
        return True

    def scrape_loop(self, source):
        to_crawl = self.db_urls.search((where('source')==source) & (where('crawled') == False))
        pbar = tqdm([t.doc_id for t in to_crawl])
        for i in pbar:
            pbar.set_description("Processing id:{}".format(i))
            start = time.time()
            self.scrape_article(i)
            end = time.time()
            if i%self.consecutive_crawls == 0:
                delay = end - start
                time.sleep(self.base_sleep_time + (delay*self.sleep_increase_ratio))

        self.driver.quit() # kill chromedriver process


class ElTiempo(NewsSource):
    def __init__(self,
        url,
        r_url,
        options=selenium_opt(),
        consecutive_crawls=10, #urls
        base_sleep_time=20, #seconds
        sleep_increase_ratio=1.5, #percentaje
        dbs_path = './'

    ):
        super().__init__(url, options, consecutive_crawls, base_sleep_time, sleep_increase_ratio, dbs_path)
        self.r_url = r_url

    def get_n_pages(self):
        pgs = self.driver.find_elements_by_css_selector(".pagination>ul>li")
        max_pages=max([int(p.text) for p in pgs if p.text.isdigit()])
        return max_pages

    def get_article_url(self, element):
        title = element.find_elements_by_class_name('title')[0].text
        url = element.find_elements_by_class_name('title')[0].get_attribute('href')
        epigraph = element.find_elements_by_class_name('epigraph')[0].text
        unix_date = element.find_elements_by_class_name('published-at')[0].get_attribute('published-unix')
        return {
            'title': title,
            'url': url,
            'source': 'El Tiempo',
            'crawled': False,
            'extra': {
                'unix_date': unix_date,
                'ephigraph': epigraph
            }
        }

    def get_articles(self, max_pages=None, skip_on_overlap=False):
        if not max_pages: max_pages=self.get_n_pages()
        else: max_pages = min(max_pages, self.get_n_pages())

        for i in trange(1, max_pages + 1):
            start = time.time()
            self.driver.get(self.r_url.format(i))
            end = time.time()
            elements = self.driver.find_elements_by_css_selector('.listing>.listing')
            for e in elements:
                info = self.get_article_url(e)
                if not self.store_url(info) and skip_on_overlap: #overlap
                    return False
            if i%self.consecutive_crawls == 0:
                delay = end - start
                time.sleep(self.base_sleep_time + (delay*self.sleep_increase_ratio))
        return True

    def scrape_article(self, db_urls_id):
        url_info = self.db_urls.get(doc_id=db_urls_id)
        url = url_info['url']
        self.driver.get(url)

        # There might be content that is not text (like a video)
        try:
            content = self.driver.find_element_by_class_name('articulo-contenido')
            content_elems = content.find_elements_by_class_name('contenido')
            txt = []
            for e in content_elems:
                txt+=[t for t in e.text.rsplit('\n') if len(t)>0 and t[0]!='(']
            txt = ' '.join(txt)
        except:
            txt = None

        # Opinion articles/videos/other usually do not have tags
        try:
            tags = [t.text for t in self.driver.find_elements_by_css_selector('.tags-en-articulo-links.tag-related')[0]\
                .find_elements_by_class_name('tags-en-articulo-tag')]
        except:
            tags = None

        date = datetime.datetime.fromtimestamp(int(url_info['extra']['unix_date'])).strftime("%Y-%m-%d")
        # store
        self.db_crawled.insert({
            'title': url_info['title'],
            'source': url_info['source'],
            'date': date,
            'article': txt,
            'extra':{
                'tags': tags
            }
        })

        url_info['crawled']=True
        self.db_urls.update(url_info, doc_ids=[db_urls_id])

    def scrape_loop(self):
        super().scrape_loop('El Tiempo')

class Semana(NewsSource):
    def __init__(
        self,
        search_term,
        options=selenium_opt(),
        consecutive_crawls=10, #urls
        base_sleep_time=20, #seconds
        sleep_increase_ratio=1.5, #percentaje
        dbs_path='./'
    ):
        url = 'https://www.semana.com/buscador/'
        super().__init__(url, options, consecutive_crawls, base_sleep_time, sleep_increase_ratio, dbs_path)
        self.search_term = search_term

    def get_article_url(self, element):
        title = element.find_element_by_class_name('card-title').text
        url = element.find_element_by_css_selector('.styles__TitleItem-n367ec-5.lobgrU>a').get_attribute('href')
        summary = element.find_element_by_class_name('fFWIIi').text
        date = element.find_element_by_css_selector('.styles__TextItem-n367ec-6.kkATsm').text

        return {
            'title': title,
            'url': url,
            'source': 'Semana',
            'crawled': False,
            'extra': {
                'string_date': date,
                'summary': summary
            }
        }

    def get_articles(self, dates:dict):
        assert dates['start'] < dates['end']
        try:
            search_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.styles__Text-sc-4fped1-7.buBloz'))
            )
            search_field.clear()
            search_field.send_keys(self.search_term)
            self.driver.find_element_by_css_selector('.styles__BotonBusqueda-sc-4fped1-5.UKTIZ').click()

            time.sleep(2)
            elem_pages = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.styles__Title-sc-4fped1-2.cATexO'))
            ).text
            pages = (int(re.findall(r'[0-9]+', elem_pages)[-1]) // 20) + 1
            with tqdm(total=pages) as pbar:
                i = 1
                while True:
                    #pbar.set_description("Page {} / {} (may stop earlier)".format(i, pages))
                    pbar.update(1)
                    start = time.time()
                    element_grid = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.styles__ContenedorLista-sc-4fped1-11.fGlrDg'))
                    )
                    elements=element_grid.find_elements_by_css_selector('.styles__GridItem-n367ec-3')
                    end = time.time()

                    breakWhile=False
                    for e in elements:
                        info = self.get_article_url(e)
                        date = datetime.date.fromisoformat(info['extra']['string_date'])
                        if date < dates['start']:
                            breakWhile=True
                            break
                        elif date <= dates['end'] and date >= dates['start']:
                            self.store_url(info)

                    if breakWhile: break
                    try:
                        next_button = self.driver.find_element_by_css_selector('.styles__BotonMasResultados-sc-4fped1-10.khuijj')
                        next_button.click()
                        time.sleep(2) # I guess it is ok while the page updates the contents
                    except:
                        break

                    if i % self.consecutive_crawls == 0:
                        delay = end - start
                        time.sleep(self.base_sleep_time + (delay*self.sleep_increase_ratio))
                    i+=1
                pbar.n=pages
                pbar.refresh()
        except Exception:
            raise Exception
        return True

    def scrape_article(self, db_urls_id):
        url_info = self.db_urls.get(doc_id=db_urls_id)
        url = url_info['url']
        if url in ['', 'https://www.semana.com/buscador/']: return # just in case there is no url
        self.driver.get(url)

        txt = None
        date = url_info['extra']['string_date']
        try:
            tags = [t.text for t in self.driver.find_element_by_class_name('tags-list')\
                .find_elements_by_class_name('tags-list-item')]
        except:
            tags = None

        # store
        self.db_crawled.insert({
            'title': url_info['title'],
            'source': url_info['source'],
            'date': date,
            'article': txt,
            'extra':{
                'tags': tags
            }
        })

        url_info['crawled']=True
        self.db_urls.update(url_info, doc_ids=[db_urls_id])
        '''
            TODO:
            - Need to bypass semana paywall... easy if we block p.js from the sources downloaded.
            Semana does not work without javascript so we can't block it.
            - CHECK. Crawl tags
        '''
    def scrape_loop(self):
        super().scrape_loop('Semana')
