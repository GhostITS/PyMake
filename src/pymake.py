import json
import threading
import copy
import subprocess
import os
import time
from typing import List, Dict

import jsonschema

from util import(LOG_ERR, LOG_INFO)


gPMakeSchema = {
    "definitions":
    {
        "array_str":
        {
            "$id": "array_str",
            "type": "array",
            "items": {"type": "string"}
        },

        "target_item":
        {
            "type": "object",
            "properties":
            {
                "name": {"type": "string"},
                "depend": {"$ref": "array_str"},
                "cmd": {"$ref": "array_str"},
            }
        }
    },
    "type": "object",
    "properties":
    {
        "path": {"$ref": "array_str"},
        "target": {
            "type": "array",
            "items": {"$ref": "#/definitions/target_item"}
        }
    },
    "required": ["target"]
}


class Task:
    class TaskState:
        Todo = 0
        Doing = 1
        Done = 2

    def __init__(self) -> None:
        self.name = ""
        self.depend = []
        self.cmd = []
        self.state = Task.TaskState.Todo
        self.depTask = {}
        self.sontask = {}

    def __str__(self) -> str:
        return json.dumps(self.__dict__)


class PyMake:
    class MakeExitEnum:
        Doing = 0
        Finish = 1
        Fail = 2

    def __init__(self, fileName: str = "PMakeFile", threadNum: int = 4) -> None:
        self._fileName = fileName
        self._threadNum = threadNum
        self._PMakeFile = None

        self._taskDataLock = threading.Lock()
        self._taskMap: Dict[str, Task] = {}
        self._taskQue: List[Task] = []
        self._taskTotal = 0
        self._taskFinish = 0
        self._MakeExit = PyMake.MakeExitEnum.Doing

    def SetFileName(self, fileName) -> None:
        self._fileName = fileName

    def Load(self) -> int:
        contents = ""
        PMakeFleTmp:List[str] = None
        try:
            with open(self._fileName, encoding='utf-8') as file:
                PMakeFleTmp = json.load(file)
                if PyMake.CheckFile(PMakeFleTmp) != 0:
                    LOG_ERR("check makefile format fail")
                    return -1
        except Exception as except_result:
            LOG_ERR("read makefile fail: {0}", except_result)
            return -1

        if not "path" in PMakeFleTmp:
            PMakeFleTmp["path"] = []
        PMakeFleTmp["path"].insert(0, "./")
        self._PMakeFile = PMakeFleTmp
        return 0

    def Run(self) -> int:
        if 0 != self.Load():
            LOG_ERR("load fail")
            return -1

        if 0 != self.TaskQueInit():
            LOG_ERR("taskque init fail")
            return -1

        threadList: List[threading.Thread] = []
        for i in range(self._threadNum):
            worker = threading.Thread(target=self.TaskWorker)
            worker.start()
            threadList.append(worker)

        # for worker in threadList:
        #     worker:threading.Thread = worker
        #     worker.join()
        bAlive = True
        try:
            while bAlive:
                bAlive = False
                for worker in threadList:
                    if worker.is_alive():
                        bAlive = True
                        break
                time.sleep(0.01)
        except KeyboardInterrupt:
            print(">>>>>>>")
            self._MakeExit = PyMake.MakeExitEnum.Fail

        if self._MakeExit != PyMake.MakeExitEnum.Finish:
            LOG_INFO("make fail!")
            return -1
        else:
            LOG_INFO("make finish!")
        return 0

    def CheckFile(PMakeFile) -> int:
        try:
            jsonschema.validate(instance=PMakeFile, schema=gPMakeSchema)
        except jsonschema.ValidationError as except_result:
            LOG_ERR("checkfile fail:{0}", except_result)
            return 1
        except Exception as except_result:
            LOG_ERR("checkfile fail2:{0}", except_result)
            return -1
        return 0

    def FileExists(self, fileName):
        for dir in self._PMakeFile["path"]:
            fileNameAP = os.path.join(dir, fileName)
            if os.path.exists(fileNameAP):
                return fileNameAP
        return None

    # 获取文件修改时间，文件不存在返回None
    def GetMTime(self, fileName):
        fileName = self.FileExists(fileName)
        if fileName:
            return os.path.getmtime(fileName)
        return None

    def TaskQueInit(self) -> int:
        assert(self._PMakeFile)

        taskMap = self._taskMap
        targetList = self._PMakeFile["target"]

        #检测 目标重复
        for item in targetList:
            taskName = item["name"]
            if taskName in taskMap:
                LOG_ERR("target repeat {0}", taskName)
                return -1
            oneTask = Task()
            oneTask.name = taskName
            oneTask.cmd = item["cmd"]
            oneTask.depend = item["depend"]

            taskMap[taskName] = oneTask
            self._taskTotal = self._taskTotal + 1

        #TODO 检测 依赖循环 def dfs

        #把最前置的任务加入任务队列
        for item in targetList:
            taskName = item["name"]
            oneTask: Task = taskMap.get(taskName, None)
            assert(oneTask)

            depend = item["depend"]
            bHaveFatherTask = False
            for depItem in depend:
                depTask: Task = taskMap.get(depItem, None)
                if depTask:
                    bHaveFatherTask = True
                    oneTask.depTask[depItem] = True
                    depTask.sontask[taskName] = True
            if not bHaveFatherTask:
                oneTask.state = Task.TaskState.Doing
                self._taskQue.append(oneTask)

        for _, itemTask in self._taskMap.items():
            LOG_INFO("{0}", itemTask)
        return 0

    def TaskWorker(self) -> None:
        bRuning = True
        MakeExit = None
        while bRuning:
            self._taskDataLock.acquire(blocking=True)
            oneTask: Task = None
            bRuning = (self._MakeExit == PyMake.MakeExitEnum.Doing)
            if len(self._taskQue) > 0:
                oneTask = copy.copy(self._taskQue.pop())
            self._taskDataLock.release()

            if not bRuning:
                break

            if not oneTask:
                time.sleep(0.001)
                #yield
                continue

            # 依赖文件不存在
            maxDepMTime = 0
            for dep in oneTask.depend:
                if not self.FileExists(dep):
                    LOG_ERR("dep not found: {0}", dep)
                    MakeExit = PyMake.MakeExitEnum.Fail
                    break
                else:
                    maxDepMTime = max(maxDepMTime, self.GetMTime(dep))
            if MakeExit != None:
                break

            
            if self.FileExists(oneTask.name) and self.GetMTime(oneTask.name) >= maxDepMTime:
                LOG_INFO("skip task:{0}", oneTask.name)
            else:
                LOG_INFO("doing task:{0}", oneTask.name)
                LOG_INFO("cmd:{0}", oneTask.cmd)
                for cmd in oneTask.cmd:
                    try:
                        #TODO 这个方法貌似在某些情况会有问题
                        popen = subprocess.Popen(cmd, shell=True)
                        ret = popen.wait()
                    except Exception as except_result:
                        LOG_ERR("{0}", except_result)
                        ret = -1

                    if ret != 0:
                        LOG_ERR("exec task[{0}] fail:{1}",
                                oneTask.name, oneTask.cmd)
                        MakeExit = PyMake.MakeExitEnum.Fail
                        bRuning = False
                        break
                LOG_INFO("finish task:[{0}]", oneTask.name)

            if not self.FileExists(oneTask.name) or self.GetMTime(oneTask.name) < maxDepMTime:
                LOG_ERR("target gen fail, task[{0}]", oneTask.name)
                MakeExit = PyMake.MakeExitEnum.Fail
                bRuning = False

            if not bRuning:
                break

            self._taskDataLock.acquire(blocking=True)
            # 标记任务完成
            oneTask: Task = self._taskMap.get(oneTask.name, None)
            assert(oneTask != None)
            oneTask.state = Task.TaskState.Done
            self._taskFinish = self._taskFinish + 1
            if self._taskFinish >= self._taskTotal:
                self._MakeExit = PyMake.MakeExitEnum.Finish

            LOG_INFO("process {0}/{1}", self._taskFinish, self._taskTotal)

            # 检测后继任务是否可以执行，可以则将后继任务放入任务队列
            for son in oneTask.sontask:
                sonTask: Task = self._taskMap.get(son, None)
                assert(sonTask != None)
                if sonTask.state == Task.TaskState.Todo:
                    canDoingTask = True
                    for dep in sonTask.depTask:
                        depTask: Task = self._taskMap.get(dep, None)
                        assert(depTask != None)
                        if depTask.state != Task.TaskState.Done:
                            canDoingTask = False
                            break
                    if canDoingTask:
                        sonTask.state = Task.TaskState.Doing
                        self._taskQue.append(sonTask)
            self._taskDataLock.release()

        if MakeExit != None:
            self._taskDataLock.acquire(blocking=True)
            self._MakeExit = MakeExit
            self._taskDataLock.release()

        LOG_INFO("worker thread[{0}] exit", threading.current_thread().ident)
