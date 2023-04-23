import threading

def LOG_INFO(fmt, *args):
    print("tid[{:>6}] INFO  ".format(threading.current_thread().ident) + fmt.format(*args))

def LOG_ERR(fmt, *args):
    print("tid[{:>6}] ERROR ".format(threading.current_thread().ident) +  fmt.format(*args))