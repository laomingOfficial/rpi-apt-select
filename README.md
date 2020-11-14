# rpi-apt-select

## Features  
- All mirrors are scrap from https://www.raspbian.org/RaspbianMirrors 
- Test latency to all mirrors
- Generate sources.list & raspi.list

## 功能(简体)  
- 在https://www.raspbian.org/RaspbianMirrors 爬源
- 测试每个源的延迟
- 生成sources.list 和 raspi.list

## 功能(繁体)  
- 在https://www.raspbian.org/RaspbianMirrors 爬源
- 測試每個源的延遲
- 生成sources.list 和 raspi.list
 
Version: v1.0 Alpha  
Kindly inform me if there is any issues/bugs.  
如有问题/小虫请联系我。
如有問題/小蟲請聯係我。

```
Installation Steps/安装步骤/安裝步驟:
1. git clone https://github.com/laomingOfficial/rpi-apt-select
2. pip3 install tcp_latency tldextract beautifulsoup4

Execute/运行/運行:
python3 rpi-apt-select.py

# software apt source/软件更新源/軟體更新源
sudo cp /etc/apt/sources.list sources.list.backup && sudo mv sources.list /etc/apt/

# system apt source/系统更新源/系統更新源
sudo cp /etc/apt/sources.list.d/raspi.list raspi.list.backup && sudo mv raspi.list /etc/apt/sources.list.d/
```