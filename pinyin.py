import argparse
import model
import sys
import pypinyin
import tqdm
from time import time

def readSeq(inputFile):
    f = open(inputFile, "r", encoding="utf-8-sig")
    seqList = [s.strip().split(" ") for s in f.readlines()]
    f.close()
    return seqList

def writeSeq(outputFile, outSeqList):
    f = open(outputFile, "w")
    for seq in outSeqList:
        f.write(seq + "\n")
    f.close()

def main():
    # inputFile = sys.argv[1]
    # outputFile = sys.argv[2]

    parser = argparse.ArgumentParser(description="gyx's pinyin")
    parser.add_argument("--input", action="store", default="", help="input pinyin file")
    parser.add_argument("--output", action="store", default="", help="output Chinese file")
    parser.add_argument("--load", action="store", default="", help="load model path")
    parser.add_argument("--alpha", action="store", default=0.9, type=float, help="alpha for laplacian smooth for 2-gram")
    parser.add_argument("--beta", action="store", default=0.0, type=float, help="beta for laplaciian smooth for 3-gram")
    parser.add_argument("--train", action="store", default="", help="train the model, input train file")
    parser.add_argument("--n_gram", action="store", default=2, type=int, help="use n_gram model")
    parser.add_argument("--save_dir", action="store", default="", help="the dir where the model been saved")
    parser.add_argument("--threshold", action="store", default=1, type=int, help="number of items not larger than threshold will be cut")
    parser.add_argument("--single_yin", action="store_true", default=False, help="enable double yin")
    parser.add_argument("--p_threshold", action="store", default=0.001, help="probability lower than p_threshold will be cut")
    parser.add_argument("--topNum", action="store", default=5, type=int, help="top number")
    parser.add_argument("--beginCut", action="store", default=6, type=int, help="begin_cut")
    parser.add_argument("--valid", action="store", help="validate file")
    parser.add_argument("--testOut", action="store", help="test file output")
    args = parser.parse_args()

    pinyinModel = model.Model("./data/pinyin2ch.txt", "./data/all-ch.txt", args)
    if args.train:
        print("processing data...")
        data = open(args.train, "r").read()
        print("start trainning")
        pinyinModel.train(data)
        pinyinModel.save(args.save_dir)
    else:
        print("loading model")
        pinyinModel.load(args.load)
        print("load succeed")
        if args.input:
            seqList = readSeq(args.input)
            outSeqList = []
            startTime = time()
            for seq in tqdm.tqdm(seqList):
                outSeqList.append("".join(pinyinModel(seq)))
            endTime = time()
            writeSeq(args.output, outSeqList)
            if args.testOut:
                vf = open(args.valid, "r")
                validSeqList = vf.readlines()
                badCaseList = []
                for out, valid in tqdm.tqdm(zip(outSeqList, validSeqList)):
                    if not out == valid.strip():
                        badCaseList.append((out, valid))
                vf.close()
                tf = open(args.testOut, "w")
                tf.write("correct: " + str(1 - len(badCaseList) / len(validSeqList)) + " time: " + str(endTime - startTime) + "\n\n")
                tf.write("badCase:\n")
                for out, valid in badCaseList:
                    tf.write(out + "\n" + valid + "\n\n")
                vf.close()
        else:
            while True:
                seq = input("Input pinyin sequence: ").strip().split(" ")
                outSeq = pinyinModel(seq)
                print("".join(outSeq))

if __name__ == "__main__":
    main()
