import numpy
import os
import json
import tqdm

class Model(object):
    def __init__(self, p2cFile, allChFile, n_gram = 2, alpha = 0.9, beta = 0):
        # n gram model
        self.n_gram = n_gram
        # pinyin to character
        self.p2cFile = p2cFile
        self.p2cDict = self.loadPinyin2Ch(p2cFile)
        # all characters file
        self.allCh = open(allChFile, "r").read()
        # pTable[n] for n continuous character
        self.pTable = []
        # number of single characters
        self.numSingle = 0
        # Laplacian soomth for 2-gram
        self.alpha = alpha
        # Laplacian soomth for 3-gram
        self.beta = beta

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


    def train(self, data):
        rawSingleChNum = len(data)
        if self.n_gram >= 1:
            print("1_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(rawSingleChNum)):
                ch = data[i]
                if ch in self.allCh:
                    self.pTable[0][ch] = self.pTable[0][ch] + 1 if ch in self.pTable[0] else 1
                    self.numSingle += 1

        if self.n_gram >= 2:
            print("2_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(1, rawSingleChNum)):
                if data[i - 1] in self.allCh and data[i] in self.allCh:
                    self.pTable[1][data[i - 1 : i + 1]] = self.pTable[1][data[i - 1 : i + 1]] + 1 if data[i - 1 : i + 1] in self.pTable[1] else 1

        if self.n_gram >= 3:
            print("3_gram start")
            self.pTable.append({})
            for i in tqdm.tqdm(range(2, rawSingleChNum)):
                if data[i - 2] in self.allCh and data[i - 1] in self.allCh and data[i] in self.allCh:
                    self.pTable[2][data[i - 2 : i + 1]] = self.pTable[2][data[i - 2 : i + 1]] + 1 if data[i - 2 : i + 1] in self.pTable[2] else 1

    def save(self, model_dir):
        path = os.path.join(model_dir, str(self.n_gram) + "-gram-model.model")
        f = open(path, "w")
        hyperInfo = {"numSingle": self.numSingle, "n_gram": self.n_gram}
        f.write(json.dumps(hyperInfo))
        f.write("\n")
        f.write(json.dumps(self.pTable, ensure_ascii=False))
        f.close()


    def load(self, modelPath):
        f = open(modelPath, "r")
        temp = f.readlines()
        hyperInfo = json.loads(temp[0])
        self.n_gram = hyperInfo["n_gram"]
        self.numSingle = hyperInfo["numSingle"]
        self.pTable = json.loads(temp[1])
        f.close()

    def loadPinyin2Ch(self, p2cFile):
        f = open(p2cFile, "r", encoding="utf-8-sig")
        p2cDict = {}
        for line in f.readlines():
            tempList = line.strip().split(" ")
            p2cDict[tempList[0]] = tempList[1:]
        return p2cDict

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
                    # if seqChL[0][last] + seqChL[1][cur] == "清华":
                    #     print("init prob1:", prob1, "init prob2:", prob2, A[1][cur][last], last, cur)
                    # if seqChL[0][last] + seqChL[1][cur] == "氰化":
                    #     print("init prob1:", prob1, "init prob2:", prob2, A[1][cur][last], last, cur)

    def dp3(self, A, seqChL):
        """3-gram dp"""
        seqLen = len(seqChL)
        #init A
        for cur in range(0, len(A[0])):
            prob = 0
            if seqChL[0][cur] in self.pTable[0]:
                prob = self.pTable[0][seqChL[0][cur]] / self.numSingle
            A[0][cur] = (prob, 0)
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
                # if seqChL[0][last1] + seqChL[1][cur] == "清华":
                #     print("init prob1:", prob1, "init prob2:", prob2, A3[1][cur][last1], last1, cur)
                # if seqChL[0][last1] + seqChL[1][cur] == "氰化":
                #     print("init prob1:", prob1, "init prob2:", prob2, A3[1][cur][last1], last1, cur)

        for p in range(2, seqLen):
            # print("p len:", seqChL[p])
            for cur in range(len(seqChL[p])):
                # print("p - 1 len:", seqChL[p - 1])
                for last1 in range(len(seqChL[p - 1])):
                    # print("p - 2 len:", seqChL[p - 2])
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
                        # print("prob1: ", prob1, "prob2: ", prob2, "prob3: ", prob3)
                        prob = self.beta * prob3 + self.alpha * prob2 + (1 - self.beta - self.alpha) * prob1
                        if A3[p][cur][last1] < prob * A3[p - 1][last1][last2]:
                            A3[p][cur][last1] = prob * A3[p - 1][last1][last2]

        #convert A3 to A
        for p in range(1, seqLen):
            for cur in range(len(A3[p])):
                for last1 in range(len(A3[p][cur])):
                    # if seqChL[0][last1] + seqChL[1][cur] == "清华":
                        # print("A3:", A3[p][cur][last1])
                    # print(p, cur, last1)
                    if A3[p][cur][last1] > A[p][cur][0]:
                        A[p][cur] = (A3[p][cur][last1], last1)
        # print(A3[1][3][19])
