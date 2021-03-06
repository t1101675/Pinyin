import numpy
import os
import json
import tqdm
import struct
import re
import heapq
from pypinyin import pinyin, lazy_pinyin
from string import digits

class Model(object):
    def __init__(self, p2cFile, allChFile, args):
        # n gram model
        self.n_gram = args.n_gram
        # enable double yin
        self.dbYin = not args.single_yin
        # all characters file
        self.allChFile = allChFile
        self.allCh = ""
        self.allCh2idx = {}
        self.loadAllCh()
        # pinyin to character
        self.p2cFile = p2cFile
        self.p2cDict = {}
        self.pinyin2idx = {}
        self.loadPinyin2Ch()
        # pTable[n] for n continuous character
        self.pTable = []
        # number of single characters
        self.numSingle = 0
        # Laplacian soomth for 2-gram
        self.alpha = args.alpha
        # Laplacian soomth for 3-gram
        self.beta = args.beta
        # threshold to cut low number items
        self.threshold = args.threshold
        # threshold to cut low probability
        self.p_threshold = args.p_threshold
        # the length to begin cut last1
        self.beginCut = args.beginCut
        # number of last1 words with top probability
        self.topNum = args.topNum
        # test
        self.test = args.testOut
        # special pinyin in pypinyin
        self.convertT = {"lve": "lue", "nve": "nue", "n": "en", "we": "wei", "sh": "shi", "f": "feng", "m": "mu"}

    def __call__(self, seq):
        seqLen = len(seq)
        try:
            seqChL = [self.p2cDict[p] for p in seq]
        except(KeyError):
            return ["invalid pinyin"]

        A = [[(0, 0, 0) for ch in L] for L in seqChL] #matrix for dp. every element: (probability, index of the character)
        if self.n_gram == 2:
            self.dp2(A, seqChL)
        elif self.n_gram == 3:
            self.dp3(A, seqChL)

        max_i, max_p = 0, 0
        for i in range(len(A[seqLen - 1])):
            if max_p < A[seqLen - 1][i][0]:
                max_i, max_p = i, A[seqLen - 1][i][0]
        # print(max_p)
        chSeq = [self.allCh[int(seqChL[seqLen - 1][max_i].split("/")[0])]]
        k = seqLen - 1
        while k >= 1:
            max_i = A[k][max_i][1]
            k -= 1
            chSeq.append(self.allCh[int(seqChL[k][max_i].split("/")[0])])
        return list(reversed(chSeq))

    def preprocess(self, rawData):
        """
        1. mark pinyin
        2. encode charactor
        """
        print("spliting data")
        dataL = re.split("[，。“”、：！？（）.《》￥@/%]|[0-9]|[a-z]|[A-Z]", rawData)
        print("removing characters not concerned")
        data = []
        for i in tqdm.tqdm(range(len(dataL))):
            data.append("")
            for ch in dataL[i]:
                if ch in self.allCh2idx:
                    data[-1] += ch

        if self.dbYin:
            print("marking pinyin")
            pinyinList = []
            for i in tqdm.tqdm(range(len(data))):
                pinyinList.append(lazy_pinyin(data[i]))
        dataProcessed = []

        print("preprocessing")
        for i in tqdm.tqdm(range(len(data))):
            tempProcessed = []
            for j in range(len(data[i])):
                if self.dbYin:
                    try:
                        if pinyinList[i][j] in self.convertT:
                            pinyinIdx = self.pinyin2idx[self.convertT[pinyinList[i][j]]]
                        else:
                            pinyinIdx = self.pinyin2idx[pinyinList[i][j]]
                    except(KeyError):
                        print(data[i][j], pinyinList[i][j])
                    tempProcessed.append(str(self.allCh2idx[data[i][j]]) + "/" + str(pinyinIdx) + "/")
                else:
                    tempProcessed.append(str(self.allCh2idx[data[i][j]]) + "/")
            dataProcessed.append(tempProcessed)
        return dataProcessed

    def train(self, data):
        pcd = self.preprocess(data) #processed data
        pcdLen = len(pcd)
        if self.n_gram >= 1:
            print("1_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(pcdLen)):
                for j in range(len(pcd[i])):
                    ch = pcd[i][j]
                    self.pTable[0][ch] = self.pTable[0][ch] + 1 if ch in self.pTable[0] else 1
                    self.numSingle += 1

        if self.n_gram >= 2:
            print("2_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(pcdLen)):
                for j in range(1, len(pcd[i])):
                    ch = pcd[i][j - 1] + pcd[i][j]
                    self.pTable[1][ch] = self.pTable[1][ch] + 1 if ch in self.pTable[1] else 1
            self.pTable[1] = self.cutItem(self.pTable[1], self.threshold)

        if self.n_gram >= 3:
            print("3_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(pcdLen)):
                for j in range(2, len(pcd[i])):
                    ch = pcd[i][j - 2] + pcd[i][j - 1] + pcd[i][j]
                    self.pTable[2][ch] = self.pTable[2][ch] + 1 if ch in self.pTable[2] else 1
            self.pTable[2] = self.cutItem(self.pTable[2], self.threshold)

    def cutItem(self, dict, threshold):
        dictCut = {}
        for key, value in dict.items():
            if value > threshold:
                dictCut[key] = value
        return dictCut

    def save(self, model_dir):
        print("saving model")
        if self.dbYin:
            path = os.path.join(model_dir, str(self.n_gram) + "-gram-" + str(self.threshold) + "-cut-dy.model")
        else:
            path = os.path.join(model_dir, str(self.n_gram) + "-gram-" + str(self.threshold) + "-cut.model")
        f = open(path, "wb")
        # hyperinfo: 32b + 32b + 8b(numSingle, n_gram, dbYin)
        hyperInfo = struct.pack("II?", self.numSingle, self.n_gram, self.dbYin)
        # n-gram block (32b + 32b) * n + 32b ((character, pinyin) * n, count)

        pBlock = [bytearray() for n in range(self.n_gram)]
        sizes = bytearray()
        for n in range(self.n_gram):
            print("saving for " + str(n + 1) + "_gram")
            tempBlockItemList = []
            for key, value in tqdm.tqdm(self.pTable[n].items()):
                #key, value = self.pTable[n].items()[i]
                tempL = [int(x) for x in key.split("/")[0:-1]] #the last one is ""
                # print(tempL)
                for x in tempL:
                    pBlock[n] += struct.pack("H", x)
                pBlock[n] += struct.pack("I", value)
            sizes += struct.pack("I", len(self.pTable[n]))

        f.write(hyperInfo + sizes + b"".join(pBlock))
        f.close()


    def load(self, modelPath):
        f = open(modelPath, "rb")
        self.numSingle, self.n_gram, dbYin = struct.unpack("II?", f.read(9))

        if not self.dbYin == dbYin:
            print("The model file is for double yin but this model disabled it")
            exit()

        sizes = [struct.unpack("I", f.read(4))[0] for n in range(self.n_gram)]
        chLen = 2 if self.dbYin else 1
        for n in range(len(sizes)):
            self.pTable.append({})
            for i in range(sizes[n]):
                t = struct.unpack(str(chLen * (n + 1)) + "H", f.read(2 * chLen * (n + 1)))
                key = "/".join([str(x) for x in t]) + "/"
                value, = struct.unpack("I", f.read(4))
                self.pTable[n][key] = value
        f.close()

    def loadPinyin2Ch(self):
        f = open(self.p2cFile, "r", encoding="utf-8-sig")
        idx = 0
        for line in f.readlines():
            tempList = line.strip().split(" ")
            if self.dbYin:
                self.p2cDict[tempList[0]] = [str(self.allCh2idx[ch]) + "/" + str(idx) + "/" for ch in tempList[1:]]
            else:
                self.p2cDict[tempList[0]] = [str(self.allCh2idx[ch]) + "/" for ch in tempList[1:]]
            self.pinyin2idx[tempList[0]] = idx
            idx += 1

    def loadAllCh(self):
        self.allCh = open(self.allChFile, "r").read()
        for i in range(len(self.allCh)):
            self.allCh2idx[self.allCh[i]] = i

    def dp2(self, A, seqChL):
        """2-gram dp"""
        seqLen = len(seqChL)
        # dp initial
        for cur in range(0, len(A[0])):
            prob = 0
            if seqChL[0][cur] in self.pTable[0]:
                prob = self.pTable[0][seqChL[0][cur]] / self.numSingle
            A[0][cur] = (prob, 0, cur)
        # dp: A[p][cur] = max{A[p - 1][last] * prob_{cur}{last} | for all last}
        for p in range(1, seqLen):
            for cur in range(len(seqChL[p])):
                for last in range(len(seqChL[p - 1])):
                    prob1, prob2 = 0, 0
                    if seqChL[p][cur] in self.pTable[0]:
                        #p(W_{i}) = count(W_{i}) / num_single
                        prob1 = self.pTable[0][seqChL[p][cur]] / self.numSingle
                        if seqChL[p - 1][last] + seqChL[p][cur] in self.pTable[1]:
                            #p(W_{i} | W_{i - 1}) = count(W_{i - 1}W_{i}) / count(W_{i - 1})
                            prob2 = self.pTable[1][seqChL[p - 1][last] + seqChL[p][cur]] / self.pTable[0][seqChL[p - 1][last]]
                    #p = alpha * p(W_{i} | W_{i - 1}) + (1 - alpha) * p(W_{i})

                    prob = self.alpha * prob2 + (1 - self.alpha) * prob1
                    if A[p][cur][0] < prob * A[p - 1][last][0]:
                        A[p][cur] = (prob * A[p - 1][last][0], last, cur)

    def dp3(self, A, seqChL):
        """3-gram dp"""
        seqLen = len(seqChL)
        topProbList = [[] for p in range(0, seqLen)]
        #init A
        for cur in range(0, len(A[0])):
            prob = 0
            if seqChL[0][cur] in self.pTable[0]:
                prob = self.pTable[0][seqChL[0][cur]] / self.numSingle
            A[0][cur] = (prob, 0, cur)
        topProbList[0] = list(zip(*heapq.nlargest(self.topNum, A[0], key=lambda key: key[0])))[2]

        if seqLen <= 1:
            return
        # A3[p][cur][last], expand of A
        A3 = [ [0 for chCur in seqChL[0]] ] # place holder
        A3 += [ [ [ 0 for chLast in seqChL[i - 1]] for chCur in seqChL[i] ] for i in range(1, seqLen)]
        # dp initial A3[1][*][*]
        for cur in range(0, len(A3[1])):
            for last1 in range(0, len(A3[1][cur])):
                prob1, prob2 = 0, 0
                if seqChL[1][cur] in self.pTable[0]:
                    prob1 = self.pTable[0][seqChL[1][cur]] / self.numSingle
                    if seqChL[0][last1] + seqChL[1][cur] in self.pTable[1]:
                        prob2 = self.pTable[1][seqChL[0][last1] + seqChL[1][cur]] / self.pTable[0][seqChL[0][last1]]
                prob = (self.alpha + self.beta) * prob2 + (1 - self.alpha - self.beta) * prob1
                A3[1][cur][last1] = prob * A[0][last1][0]
                if A3[1][cur][last1] > A[1][cur][0]:
                    A[1][cur] = (A3[1][cur][last1], last1, cur)
        topProbList[1] = list(zip(*heapq.nlargest(self.topNum, A[1], key=lambda key: key[0])))[2]

        for p in range(2, seqLen):
            if p > self.beginCut:
                last1List = topProbList[p - 1]
                last2List = topProbList[p - 2]
            else:
                last1List = range(len(seqChL[p - 1]))
                last2List = range(len(seqChL[p - 2]))

            for cur in range(len(seqChL[p])):
                for last1 in last1List:
                    for last2 in last2List:
                        prob1, prob2, prob3 = 0, 0, 0
                        if seqChL[p][cur] in self.pTable[0]:
                            #p(W_{i}) = count(W_{i}) / num_single
                            prob1 = self.pTable[0][seqChL[p][cur]] / self.numSingle
                            if seqChL[p - 1][last1] + seqChL[p][cur] in self.pTable[1]:
                                #p(W_{i} | W_{i - 1}) = count(W_{i - 1}W_{i}) / count(W_{i - 1})
                                prob2 = self.pTable[1][seqChL[p - 1][last1] + seqChL[p][cur]] / self.pTable[0][seqChL[p - 1][last1]]
                                if seqChL[p - 2][last2] + seqChL[p - 1][last1] + seqChL[p][cur] in self.pTable[2]:
                                    #p(W_{i} | W_{i - 1}, W_{i - 2}) = count(W_{i - 2}W_{i - 1}W_{i}) / count(W_{i - 2}W_{i - 1})
                                    prob3 = self.pTable[2][seqChL[p - 2][last2] + seqChL[p - 1][last1] + seqChL[p][cur]] / self.pTable[1][seqChL[p - 2][last2] + seqChL[p - 1][last1]]
                        #p = beta * p(W_{i} | W_{i - 1}, W_{i - 2}) + alpha * p(W_{i} | W_{i - 1}) + (1 - alpha - beta) * p(W_{i})
                        prob = self.beta * prob3 + self.alpha * prob2 + (1 - self.beta - self.alpha) * prob1
                        if A3[p][cur][last1] < prob * A3[p - 1][last1][last2]:
                            A3[p][cur][last1] = prob * A3[p - 1][last1][last2]
                    if A3[p][cur][last1] > A[p][cur][0]:
                        A[p][cur] = (A3[p][cur][last1], last1, cur)
            # print(A[p])
            try:
                topProbList[p] = list(zip(*heapq.nlargest(self.topNum, A[p], key=lambda key: key[0])))[2]
            except(IndexError):
                print(A[p])
                heapq.nlargest(self.topNum, A[p], key=lambda key: key[0])
                zip(*heapq.nlargest(self.topNum, A[p], key=lambda key: key[0]))
                exit(0)
        #convert A3 to A
        # for p in range(1, seqLen):
            # for cur in range(len(A3[p])):
                # for last1 in range(len(A3[p][cur])):
                    # if A3[p][cur][last1] > A[p][cur][0]:
                        # A[p][cur] = (A3[p][cur][last1], last1)
