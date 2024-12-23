
g_mainwnd = None

def get_mainwnd():
    global g_mainwnd
    return g_mainwnd

def set_mainwnd(wnd):
    global g_mainwnd
    g_mainwnd = wnd