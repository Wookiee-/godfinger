CD ../../
CD ./update
python ./update.py
CD ../
CALL ./cleanup.bat
python ./godfinger.py --debug
PAUSE