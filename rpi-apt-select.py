from bs4 import BeautifulSoup
import requests
import tldextract
from os import getcwd
from threading import Thread
from queue import Queue, Empty
from sys import stderr, exit
from tcp_latency import measure_latency

get_input = input
_launch_url = "https://www.raspbian.org/RaspbianMirrors"


class Mirror:
    def __init__(self, url, host, rtt):
        self.url = url
        self.host = host
        self.rtt = rtt


class URLGetTextError(Exception):
    """Error class for fetching text from a URL"""
    pass


class SourcesFileError(Exception):
    """Error class for operations on an apt configuration file
       Operations include:
            - verifying/reading from the current system file
            - generating a new config file"""
    pass


class _RoundTrip(object):
    def __init__(self, url, host, result):
        self._url = url
        self._host = host
        self._result = result

    def min_rtt(self):
        rtts = []
        try:
            rtts = measure_latency(
                host=self._host, port=80, runs=5, timeout=5)
        except Exception:
            return

        rtts = list(filter(None, rtts))
        if len(rtts) > 0:
            self._result.put(Mirror(self._url, self._host, min(rtts)))


def _get_text_from_uri(url):
    try:
        result = requests.get(url)
        result.raise_for_status()
    except requests.HTTPError as err:
        raise URLGetTextError(err)

    return result.text


def _grab_mirror_source():
    urlArr = []

    print("Grabbing mirror list from %s." % (_launch_url))

    try:
        launch_html = _get_text_from_uri(_launch_url)
        print("Finish grabbing.")
    except Exception as err:
        stderr.write("connection to %s: %s\n" % (_launch_url, err))
        exit(0)
    else:
        print("Start extract RASPBIAN mirror link.")
        soup = BeautifulSoup(launch_html, "html.parser")
        divContent = soup.find(id="content")
        mirrorTable = divContent.find("table")
        mirrorRows = mirrorTable.tbody.find_all("tr")
        for tr in mirrorRows[1:]:
            urlColumn = tr.find_all("td")[3].p
            for _url in urlColumn.text.splitlines():
                if(_url.find("http") > -1):
                    _uri = _url.partition("//")[-1].strip()
                    if not _uri.endswith("/"):
                        _uri += "/"
                    _tld = tldextract.extract(_uri)
                    _host = _tld.fqdn
                    urlArr.append(("http://"+_uri, _host))

        print("Finish extract RASPBIAN mirror link.")

    return urlArr


def _ask(query):
    answer = get_input(query)
    return answer


def _get_selected_mirror(list_size):
    key = _ask("Choose a mirror (1 - %d)\n'q' to quit " % list_size)
    while True:
        try:
            key = int(key)
        except ValueError:
            if key == 'q':
                exit(0)
        else:
            if (key >= 1) and (key <= list_size):
                break

        key = _ask("Invalid entry ")

    return key


def _read_source_list_file(path):
    _configLines = []
    _configExists = False
    _configLineIndex = 0

    try:
        with open(path, 'r') as f:
            _configLines = f.readlines()
    except IOError as err:
        raise SourcesFileError((
            "Unable to read system apt file: %s" % err
        ))

    for line in _configLines:
        fields = line.split()
        if(fields[0] == "deb" and fields[1].split('://')[0] == "http"):
            _configExists = True
            break
        _configLineIndex += 1

    return (_configExists, _configLineIndex, _configLines)


def _is_url_exists(uri):
    _is_exists = True
    try:
        response = requests.get(uri, timeout=10)
        _is_exists = response.status_code < 400
    except Exception:
        _is_exists = False

    return _is_exists


class _SearchRPIMirror(object):
    def __init__(self, mirror_Raspbian, mirrorQueue_RaspberryPi):
        self._mirror_Raspbian = mirror_Raspbian
        self._mirrorQueue_RaspberryPi = mirrorQueue_RaspberryPi

    def find(self):
        if self._mirror_Raspbian.url.find("/raspbian/raspbian/") > -1:
            _newUri = self._mirror_Raspbian.url.replace(
                "/raspbian/raspbian/", "/raspberrypi/")
            if _is_url_exists(_newUri):
                self._mirrorQueue_RaspberryPi.put(
                    Mirror(_newUri, "", self._mirror_Raspbian.rtt))
        elif self._mirror_Raspbian.url.find("/raspbian/") > -1:
            _newUri = self._mirror_Raspbian.url.replace(
                "/raspbian/", "/raspberrypi/")
            if _is_url_exists(_newUri):
                self._mirrorQueue_RaspberryPi.put(
                    Mirror(_newUri, "", self._mirror_Raspbian.rtt))


def _choose_mirror(mirrorRanked, topCount):
    if len(mirrorRanked) < topCount:
        topCount = len(mirrorRanked)

    for index, mirror in enumerate(mirrorRanked[:topCount]):
        print("%2d. %.6f %s" % (index+1, mirror.rtt, mirror.url))

    return _get_selected_mirror(topCount) - 1


def _generate_source_list_file(configLines, configLineIndex, url, file_path):
    _config = configLines[configLineIndex].split()
    _config[1] = url
    configLines[configLineIndex] = ' '.join(_config)

    try:
        with open(file_path, 'w') as f:
            f.write('\n'.join(configLines))
    except IOError as err:
        raise SourcesFileError((
            "Unable to generate new sources.list:\n\t%s\n" % err
        ))


def main():
    _work_dir_Raspbian = getcwd().rstrip("/") + "/sources.list"
    _configPath_Raspbian = "/etc/apt/sources.list"
    _work_dir_RaspberryPi = getcwd().rstrip("/") + "/raspi.list"
    _configPath_RaspberryPi = "/etc/apt/sources.list.d/raspi.list"
    _topCount = 20

    print("rpi-apt-select v1.0 Alpha by LaoMing")

    (_configExists_Raspbian, _configLineIndex_Raspbian, _configLines_Raspbian) = _read_source_list_file(
        _configPath_Raspbian)
    (_configExists_RaspberryPi, _configLineIndex_RaspberryPi, _configLines_RaspberryPi) = _read_source_list_file(
        _configPath_RaspberryPi)

    if _configExists_Raspbian == False or _configExists_RaspberryPi == False:
        print("Config not exists. Byebye!")
        return

    _url_list = _grab_mirror_source()

    print("Start ping all RASPBIAN mirror for latency info.")
    threads_Raspbian = list()
    mirrorQueue_Raspbian = Queue()
    for url in _url_list:
        try:
            thread = Thread(
                target=_RoundTrip(
                    url[0], url[1], mirrorQueue_Raspbian).min_rtt,
                daemon=True
            )
            threads_Raspbian.append(thread)
        except gaierror as err:
            stderr.write("%s: %s ignored\n" % (err, url[0]))
        else:
            thread.start()

    for _, thread in enumerate(threads_Raspbian):
        thread.join()
    print("Finish ping all RASPBIAN mirror for latency info.")

    mirrorList_Raspbian = list(mirrorQueue_Raspbian.queue)
    mirrorRanked_Raspbian = sorted(
        mirrorList_Raspbian, key=lambda x: x.rtt
    )

    print("Start locate RASPBERRY PI mirror.")
    threads_RaspberryPi = list()
    mirrorQueue_RaspberryPi = Queue()
    for mirror_Raspbian in mirrorList_Raspbian:
        try:
            thread = Thread(
                target=_SearchRPIMirror(
                    mirror_Raspbian, mirrorQueue_RaspberryPi).find,
                daemon=True
            )
            threads_RaspberryPi.append(thread)
        except gaierror as err:
            stderr.write("%s: %s ignored\n" % (err, url[0]))
        else:
            thread.start()

    for _, thread in enumerate(threads_RaspberryPi):
        thread.join()

    mirrorList_RaspberryPi = list(mirrorQueue_RaspberryPi.queue)
    mirrorRanked_RaspberryPi = sorted(
        mirrorList_RaspberryPi, key=lambda x: x.rtt
    )

    print("Finish locate RASPBERRY PI mirror.")

    print("Please choose RASPBIAN mirror.")
    key = _choose_mirror(mirrorRanked_Raspbian, _topCount)
    new_mirror = mirrorRanked_Raspbian[key]
    print("Selecting mirror %(mirror)s ..." % {'mirror': new_mirror.url})

    print("Generating %s." % (_work_dir_Raspbian))
    _generate_source_list_file(
        _configLines_Raspbian, _configLineIndex_Raspbian, new_mirror.url, _work_dir_Raspbian)
    print("Generated %s." % (_work_dir_Raspbian))

    print("Please choose RASPBERRY PI mirror.")
    key = _choose_mirror(mirrorRanked_RaspberryPi, _topCount)
    new_mirror = mirrorRanked_RaspberryPi[key]
    print("Selecting mirror %(mirror)s ..." % {'mirror': new_mirror.url})

    print("Generating %s." % (_work_dir_RaspberryPi))
    _generate_source_list_file(
        _configLines_RaspberryPi, _configLineIndex_RaspberryPi, new_mirror.url, _work_dir_RaspberryPi)
    print("Generated %s." % (_work_dir_RaspberryPi))

    print("Done! Byebye~")


if __name__ == '__main__':
    main()
