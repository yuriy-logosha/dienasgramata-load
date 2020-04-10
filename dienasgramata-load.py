import datetime
import logging
import os
import time

from lxml import html

from utils import json_from_file, to_file, _poste, _gete, _get, RequestError

ss_config = 'config.json'
config = {}

try:
    config = json_from_file(ss_config, "Can't open ss-config file.")
except RuntimeError as e:
    print(e)
    exit()

resources_path = config['dienasgramata.resources.path']
if not os.path.exists(resources_path):
    os.makedirs(resources_path)

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
    def __init__(self, response, session):
        super().__init__()
        self.text = response.text
        self.response = response
        self.session = session

    def prepare(self):
        doc = html.document_fromstring(self.text)

        for meta in doc.xpath("//meta[@http-equiv='refresh']"):
            self.text = self.text.replace(meta.attrib['content'], "")

        links = doc.xpath("//head/link[@rel='stylesheet']")
        for link in links:
            try:
                r = _get(url + link.attrib['href'])
                to_file(resources_path + os.path.basename(link.attrib['href']), r.text)
            except RequestError as e:
                print(e)

        for l in links:
            self.text = self.text.replace(l.attrib['href'], os.path.basename(l.attrib['href']))

        attachments = doc.xpath("//a[@class='file']")
        for attachment in attachments:
            try:
                r = _gete(url + attachment.attrib['href'], session=self.session)[0]
                to_file(resources_path + os.path.basename(attachment.text.replace('\r', '').replace('\n', '').strip()),
                        r.content)
            except RequestError as e:
                print(e)

        for l in attachments:
            self.text = self.text.replace(l.attrib['href'],
                                          os.path.basename(l.text.replace('\r', '').replace('\n', '').strip()))


def dienasgramata(*args):
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip',
        'Accept-Language': 'en-US,en;q=0.8,ru;q=0.9,uk;q=0.7',
        'content-type': 'application/x-www-form-urlencoded'}

    d2 = datetime.date.today() + datetime.timedelta(days=3)

    r, session = _poste(url,
                        params={'v': '15', 'fake_pass': config["eklase.password"], "UserName": config["eklase.username"], "Password": config["eklase.password"]},
                        headers=headers)
    r, html_file = _gete(url + '/Family/Diary?Date=' + d2.strftime("%d.%m.%Y"), session=session, *args)

    if not r.ok:
        logger.info(r.reason)
        return

    _wrapper = VladsTimesheetResultsHTML(r, session)
    return _wrapper


logger.info("Starting " + config['logging.name'])
while True:

    try:
        dg = dienasgramata()
        dg.prepare()
        dest = resources_path + config['dienasgramata.index.name']
        logger.info("Exporting to: %s and index: %s", resources_path, dest)
        to_file(dest, dg.text)
    except Exception as e:
        logger.error(e)

    if 'restart' in config and config['restart'] > 0:
        logger.info("Waiting %s seconds.", config['restart'])
        time.sleep(config['restart'])
    else:
        exit()
