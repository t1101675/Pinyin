import argparse
import model
import sys
import pypinyin

def readSeq(inputFile):
    f = open(inputFile, "r", encoding="utf-8-sig")
    seqList = [s.strip().split(" ") for s in f.readlines()]
    f.close()
    return seqList

def writeSeq(outputFile, outSeqList):
    f = open(outputFile, "w")
    for seq in outSeqList:
        f.write("".join(seq) + "\n")
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
    args = parser.parse_args()

    pinyinModel = model.Model("./data/pinyin2ch.txt", "./data/all-ch.txt", args.n_gram, args.alpha, args.beta, args.threshold)
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
            for seq in seqList:
                outSeqList.append(pinyinModel(seq))
            writeSeq(args.output, outSeqList)
        else:
            while True:
                seq = input("Input pinyin sequence: ").strip().split(" ")
                outSeq = pinyinModel(seq)
                print("".join(outSeq))

if __name__ == "__main__":
    main()
