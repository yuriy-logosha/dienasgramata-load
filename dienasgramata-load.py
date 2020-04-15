import datetime
import logging
import os
import time

from lxml import html

from utils import json_from_file, to_file, _poste, _gete, RequestError

ss_config = 'config.json'
config = {}

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
print("Logging level", logging_level)
print("Logging format", config["logging.format"])
print("Logging file \"%s\"" % config['logging.file'])

logging.basicConfig(format=config["logging.format"], level=logging_level, handlers=[c_handler, f_handler])
logger = logging.getLogger(config["logging.name"])
logger.setLevel(logging_level)

url = config['url']


class VladsTimesheetResultsHTML:
    def __init__(self, response, resources_path):
        super().__init__()
        self.text = response.text
        self.response = response
        self.rss_path = resources_path

    def prepare(self):
        doc = html.document_fromstring(self.text)

        # TODO: Add files cleanup.
        for meta in doc.xpath("//meta[@http-equiv='refresh']"):
            self.text = self.text.replace(meta.attrib['content'], "")

        links = doc.xpath("//head/link[@rel='stylesheet']")
        for link in links:
            try:
                r = _gete(url + link.attrib['href'], session=get_session())
                to_file(self.rss_path + os.path.basename(link.attrib['href']), r.text)
                self.text = self.text.replace(link.attrib['href'], os.path.basename(link.attrib['href']))
            except Exception as e:
                print(e)

        attachments = doc.xpath("//a[@class='file']")
        for link in attachments:
            try:
                r = _gete(url + link.attrib['href'], session=get_session())
                to_file(self.rss_path + os.path.basename(link.text.replace('\r', '').replace('\n', '').strip()), r.content)
                self.text = self.text.replace(link.attrib['href'], os.path.basename(link.text.replace('\r', '').replace('\n', '').strip()))
            except RequestError as e:
                print(e)
        return self.text


session = None


def get_session():
    global session
    if not session:
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip',
            'Accept-Language': 'en-US,en;q=0.8,ru;q=0.9,uk;q=0.7',
            'content-type': 'application/x-www-form-urlencoded'}
        r, _session = _poste(url,
                            params={'v': '15', 'fake_pass': config["eklase.password"], "UserName": config["eklase.username"], "Password": config["eklase.password"]},
                            headers=headers)
        session = _session

    return session


def dienasgramata(days, resources_path, *args):
    d2 = datetime.date.today() + datetime.timedelta(days=days)

    r = _gete(url + '/Family/Diary?Date=' + d2.strftime("%d.%m.%Y"), session=get_session(), *args)

    if not r.ok:
        logger.info(r.reason)
        return

    _wrapper = VladsTimesheetResultsHTML(r, resources_path)
    return _wrapper


def check_folder(path):
    if not os.path.exists(path):
        os.makedirs(path)
    return path


logger.info("Starting " + config['logging.name'])
while True:
    try:
        for page in config["pages"]:
            rss_path = check_folder(page['resources.path'])
            dest = rss_path + page['html.name']
            logger.info("Exporting to: %s and index: %s", rss_path, dest)
            dg = dienasgramata(page['days'], rss_path)
            if dg:
                to_file(dest, dg.prepare())

    except Exception as e:
        logger.error(e)

    if 'restart' in config and config['restart'] > 0:
        logger.info("Waiting %s seconds.", config['restart'])
        session = None
        time.sleep(config['restart'])
    else:
        exit()
