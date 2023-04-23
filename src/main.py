import getopt
import sys
from pymake import PyMake

def help():
    print("python pymake.py [-f makefile] [-j threadNum] ")
    pass

gArgCfg = {
    "opt": "f:j:",
    "help": help
}

def main(argv):
    opts, args = getopt.getopt(argv, gArgCfg["opt"])

    threadNum = 4
    pMakeFile = "PMakeFile"
    for opt, arg in opts:
        if opt == "-f":
            pMakeFile = arg
        if opt == "-j":
            j = int(arg)
            if j > 0:
                threadNum = min(100, j)

    pyMake = PyMake(fileName=pMakeFile, threadNum=threadNum)
    pyMake.Run()


if __name__ == "__main__":
    main(sys.argv[1:])