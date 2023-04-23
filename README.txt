python版make工具

依赖模块：jsonschema，用于检查PMakeFile文件格式

构建描述文件：test/PMakeFile.json
测试(window):
cd test
python ../src/main.py -fPMakeFile.json -j4