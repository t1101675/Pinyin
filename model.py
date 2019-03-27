import numpy
import os
import json
import tqdm
import struct
from pypinyin import pinyin, lazy_pinyin

class Model(object):
    def __init__(self, p2cFile, allChFile, n_gram=2, alpha=0.9, beta=0, threshold=1, dbYin=True):
        # n gram model
        self.n_gram = n_gram
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
        self.alpha = alpha
        # Laplacian soomth for 3-gram
        self.beta = beta
        # threshold to cut low number items
        self.threshold = threshold
        # enable double yin
        self.dbYin = dbYin

    def __call__(self, seq):
        seqLen = len(seq)
        try:
            seqChL = [self.p2cDict[p] for p in seq]
        except(KeyError):
            print("Invalid Pinyin")
            return []

        A = [[(0, 0) for ch in L] for L in seqChL] #matrix for dp. every element: (probability, index of the character)
        if self.n_gram == 2:
            self.dp2(A, seqChL)
        elif self.n_gram == 3:
            self.dp3(A, seqChL)

        max_i, max_p = 0, 0
        for i in range(len(A[seqLen - 1])):
            if max_p < A[seqLen - 1][i][0]:
                max_i, max_p = i, A[seqLen - 1][i][0]
        # print(max_p)
        chSeq = [seqChL[seqLen - 1][max_i]]
        k = seqLen - 1
        while k >= 1:
            max_i = A[k][max_i][1]
            k -= 1
            chSeq.append(seqChL[k][max_i])
        return list(reversed(chSeq))

    def preprocess(self, data):
        """
        1. mark pinyin
        2. encode charactor
        """
        rawSingleChNum = len(data)
        if self.dbYin:
            pinyinList = lazy_pinyin(data)

        dataProcessed = []
        for i in tqdm(range(rawSingleChNum)):
            if data[i] in self.allCh2idx:
                if self.dbYin:
                    try:
                        pinyinIdx = self.pinyin2idx[pinyinList[i]]:
                    except(KeyError):
                        print(pinyinList[i])
                        exit()
                    dataProcessed.append(str(allCh2idx[data[i]]) + "/" + str(pinyinIdx) + "/")
                else:
                    dataProcessed.append(str(allCh2idx[data[i]]) + "/")
        return dataProcessed

    def train(self, data):
        print("preprocessing")
        pcd = self.preprocess(data) #processed data
        pcdLen = len(pcd)
        if self.n_gram >= 1:
            print("1_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(pcdLen)):
                ch = pcd[i]
                self.pTable[0][ch] = self.pTable[0][ch] + 1 if ch in self.pTable[0] else 1
                self.numSingle += 1

        if self.n_gram >= 2:
            print("2_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(1, pcdLen)):
                ch = pcd[i - 1] + pcd[i]
                self.pTable[1][ch] = self.pTable[1][ch] + 1 if ch in self.pTable[1] else 1
        self.pTable[1] = self.cutItem(self.pTable[1], self.threshold)

        if self.n_gram >= 3:
            print("3_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(2, pcdLen)):
                ch = pcd[i - 2] + pcd[i - 1] + pcd[i]
                self.pTable[2][ch] = self.pTable[2][ch] + 1 if ch in self.pTable[2] else 1
        self.pTable[2] = self.cutItem(self.pTable[2], self.threshold)

    def cutItem(self, dict, threshold):
        dictCut = {}
        for key, value in dict.items():
            if value > threshold:
                dictCut[key] = value
        return dictCut

    def save(self, model_dir):
        path = os.path.join(model_dir, str(self.n_gram) + "-gram-" + str(self.threshold) + "-cut-b.model")
        f = open(path, "wb")
        # hyperinfo: 32b + 32b + 8b(numSingle, n_gram, dbYin)
        hyperInfo = struct.pack("ii?", self.numSingle, self.n_gram, self.dbYin)
        # n-gram block (32b + 32b) * n + 32b ((character, pinyin) * n, count)
        pBlock = [b"" for x in range(self.n_gram)]
        sizes = b""
        for n in range(self.n_gram):
            for key, value in self.pTable[n].items():
                tempL = [int(x) for x in key.split("/")][0:-1] #the last one is ""
                for x in tempL:
                    pBlock[n] += struct.pack("H", x)
                pBlock[n] += struct.pack("H", value)
            sizes += strcut.pack("i", len(self.pTable[n]))

        # f.write(str(self.numSingle) + " " + str(self.n_gram))
        # hyperInfo = {"numSingle": self.numSingle, "n_gram": self.n_gram}
        # content = json.dumps(hyperInfo) + "\n" + json.dumps(self.pTable, ensure_ascii=False)
        # bContent = struct.pack(str(len(content)) + "s", content.encode("utf-8"))
        f.write(hyperInfo + sizes + b"".join(pBlock))
        f.close()


    def load(self, modelPath):
        f = open(modelPath, "rb")
        self.numSingle, self.n_gram, self.dbYin = struct.unpack("ii?", f.read(9))
        sizes = [strcut.unpack("i", f.read(4))[0] for n in range(self.n_gram)]
        chLen = 2 if self.dbYin else 1
        for n in len(sizes):
            for i in range(sizes[n]):
                key = "/".join(struct.unpack(str(2 * chLen * (n + 1)) + "H", f.read(2 * chLen * (n + 1)))) + "/"
                value, = struct.unpack("H", f.read(2))
                self.pTable[n][key] = value
        # temp = f.readlines()
        # hyperInfo = json.loads(temp[0])
        # self.pTable = json.loads(temp[1])
        f.close()

    def loadPinyin2Ch(self):
        f = open(self.p2cFile, "r", encoding="utf-8-sig")
        idx = 0
        for line in f.readlines():
            tempList = line.strip().split(" ")
            self.p2cDict[tempList[0]] = [str(self.allCh2idx[ch]) + "/" + str(idx) + "/" for ch in tempList[1:]]
            self.pinyin2idx[tempList[0]] = idx
            idx += 1

    def loadAllCh(self):
        self.allCh = open(self.allChFile, "r").read()
        for i in len(self.allCh):
            self.allCh2idx[self.allCh[i]] = i

    def dp2(self, A, seqChL):
        """2-gram dp"""
        seqLen = len(seqChL)
        # dp initial
        for cur in range(0, len(A[0])):
            prob = 0
            if seqChL[0][cur] in self.pTable[0]:
                prob = self.pTable[0][seqChL[0][cur]] / self.numSingle
            A[0][cur] = (prob, 0)
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
                        A[p][cur] = (prob * A[p - 1][last][0], last)

    def dp3(self, A, seqChL):
        """3-gram dp"""
        seqLen = len(seqChL)
        #init A
        for cur in range(0, len(A[0])):
            prob = 0
            if seqChL[0][cur] in self.pTable[0]:
                prob = self.pTable[0][seqChL[0][cur]] / self.numSingle
            A[0][cur] = (prob, 0)
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

        for p in range(2, seqLen):
            for cur in range(len(seqChL[p])):
                for last1 in range(len(seqChL[p - 1])):
                    for last2 in range(len(seqChL[p - 2])):
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

        #convert A3 to A
        for p in range(1, seqLen):
            for cur in range(len(A3[p])):
                for last1 in range(len(A3[p][cur])):
                    if A3[p][cur][last1] > A[p][cur][0]:
                        A[p][cur] = (A3[p][cur][last1], last1)
