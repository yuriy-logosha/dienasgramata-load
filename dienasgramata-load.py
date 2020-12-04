import datetime
import logging
import os
import re
import time

from lxml import html

from utils import json_from_file, to_file, _poste, _gete, RequestError

ss_config = 'config.json'
config = {}
session = None

try:
    config = json_from_file(ss_config, "Can't open ss-config file.")
except Exception as e:
    print(e)
    exit()

formatter = logging.Formatter(config['logging.format'])
# Create handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler(config['logging.file'])

# Create formatters and add it to handlers
c_handler.setFormatter(formatter)
f_handler.setFormatter(formatter)

logging_level = config["logging.level"] if 'logging.level' in config else 20
logging.basicConfig(format=config["logging.format"], level=logging_level, handlers=[c_handler, f_handler])
logger = logging.getLogger(config["logging.name"])
logger.setLevel(logging_level)

url = config['url']


def get_session():
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip',
        'Accept-Language': 'en-US,en;q=0.8,ru;q=0.9,uk;q=0.7',
        'content-type': 'application/x-www-form-urlencoded'}
    r, _session = _poste(url,
                         params={'v': '15', 'fake_pass': config["eklase.password"],
                                 "UserName": config["eklase.username"], "Password": config["eklase.password"]},
                         headers=headers)
    return _session


class VladsTimesheetResultsHTML:
    def __init__(self, response, resources_path):
        super().__init__()
        self.text = response.text
        self.response = response
        self.rss_path = resources_path

    def prepare(self, session):
        if not session:
            session = get_session()
        doc = html.document_fromstring(self.text)

        # TODO: Add files cleanup.
        for meta in doc.xpath("//meta[@http-equiv='refresh']"):
            self.text = self.text.replace(meta.attrib['content'], "")

        # body
        self.text = self.text.replace("<body>", "<body><div>Updated %s</div>" % time.strftime("%H:%M:%S %d.%m.%Y"))

        # header
        self.text = self.text.replace("<header>", "<header style=\"display:none\">")

        # students-journal-header
        self.text = self.text.replace("students-journal-header", "students-journal-header hidden")

        # students-journal-header-links hidden-xs
        self.text = self.text.replace("students-journal-header-links", "students-journal-header-links hidden")

        # footer-nav
        self.text = self.text.replace("class=\"footer-nav\"", "class=\"footer-nav hidden\"")

        # copyright
        self.text = self.text.replace("class=\"copyright\"", "class=\"copyright hidden\"")

        # footer
        self.text = self.text.replace("<footer>", "<footer style=\"display:none\">")

        # section-switch-item tab-pane                                               active
        self.text = self.text.replace("section-switch-item tab-pane",
                                      "section-switch-item tab-pane                                               active")

        # mobile-lessons-next
        self.text = self.text.replace("mobile-lessons-next", "mobile-lessons-next hidden")

        # mobile-lessons-prev
        self.text = self.text.replace("mobile-lessons-prev", "mobile-lessons-prev hidden")

        # scripts
        scripts = doc.xpath("//script[@src]")
        for script in scripts:
            try:
                # r = _gete(url + script.attrib['src'], session=get_session())
                # to_file(self.rss_path + os.path.basename(script.attrib['src']), r.text)
                # self.text = self.text.replace(script.attrib['src'], os.path.basename(script.attrib['src']))
                self.text = self.text.replace(script.attrib['src'], '')
            except Exception as e:
                print(e)

        links = doc.xpath("//head/link[@rel='stylesheet']")
        for link in links:
            try:
                r = _gete(url + link.attrib['href'], session=session)
                self.text = self.text.replace(link.attrib['href'], os.path.basename(link.attrib['href']))
                css_text = r.text
                css = [w for w in re.findall(r"url\(/(.*?)\)", r.text) if any(k in w for k in ['.woff', '.eot', '.ttf', '.png'])]
                for href in css:
                    try:
                        rr = _gete(url + '/' + href, session=session)
                        to_file(self.rss_path + os.path.basename(href), rr.text)
                        css_text = css_text.replace('/' + href, os.path.basename(href))
                    except Exception as ee:
                        print(ee)
                to_file(self.rss_path + os.path.basename(link.attrib['href']), css_text)
            except Exception as e:
                print(e)

        attachments = doc.xpath("//a[@class='file']")
        for link in attachments:
            try:
                r = _gete(url + link.attrib['href'], session=session)
                to_file(self.rss_path + os.path.basename(link.text.replace('\r', '').replace('\n', '').strip()),
                        r.content)
                self.text = self.text.replace(link.attrib['href'],
                                              os.path.basename(link.text.replace('\r', '').replace('\n', '').strip()))
            except RequestError as e:
                print(e)
        return self.text


def dienasgramata(days, resources_path, session, *args):
    if not session:
        session = get_session()

    d2 = datetime.date.today() + datetime.timedelta(days=days)

    r = _gete(url + '/Family/Diary?Date=' + d2.strftime("%d.%m.%Y"), session=session, *args)

    if not r.ok:
        logger.info(r.reason)
        return

    _wrapper = VladsTimesheetResultsHTML(r, resources_path)
    return _wrapper


def check_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path


if __name__ == '__main__':
    print("Logging level", logging_level)
    print("Logging format", config["logging.format"])
    print("Logging to file \"%s\"" % config['logging.file'])

    logger.info("Starting " + config['logging.name'])
    while True:
        try:
            session = get_session()
            for page in config["pages"]:
                rss_path = check_folder(page['resources.path'])
                dest = rss_path + page['html.name']
                logger.info("Exporting to: %s and index: %s", rss_path, dest)
                dg = dienasgramata(page['days'], rss_path, session)
                if dg:
                    to_file(dest, dg.prepare(session))

        except Exception as e:
            logger.error(e)

        if 'restart' in config and config['restart'] > 0:
            logger.info("Waiting %s seconds.", config['restart'])
            session = None
            time.sleep(config['restart'])
        else:
            exit()
