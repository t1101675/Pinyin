import os
import json
def collectData():
    filedir = os.getcwd() + "/sina_news_gbk"
    filenames = os.listdir(filedir)
    f = open("train-data.json", "w")
    for filename in filenames:
        if "2016" in filename:
            filepath = filedir + "/" + filename
            print("writing", filename)
            for line in open(filepath):
                f.writelines(line)
    f.close()

def getText():
    f = open("train-data.json", "r")
    f2 = open("train-data.txt", "w")
    jsonList = f.readlines()
    i = 0
    for line in jsonList:
        if line.startswith(u'\ufeff'):
            line = line.encode('utf8')[3:].decode('utf8')
        data = json.loads(line)
        if i % 5000 == 0:
            print("writing " + str(i) + "/" + str(len(jsonList)))
        # print(data)
        f2.write(data["html"])
        i += 1

def countCh():
    f = open("pinyin2ch.txt", "r")
    lenList = []
    for line in f.readlines():
        list = line.strip().split(" ")
        lenList.append(len(list))
    print(sorted(lenList))

def getSmallData():
    f = open("train-data.txt", "r")
    f2 = open("train-data-small-small.txt", "w")
    f2.write(f.read(512000))

# countCh()
getSmallData()
