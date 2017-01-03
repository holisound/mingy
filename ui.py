# coding:utf-8

import wx
from mixin import constructor
from collections import OrderedDict
import json
import os
from client import MinYuanClient
import  wx.lib.mixins.listctrl  as  listmix
import images
from event import CountEvent, EVT_COUNT, CountingThread
from datetime import datetime

def get_const():
    constfilepath = os.path.join(os.path.dirname(__file__), "const.json")
    constfilepy = os.path.join(os.path.dirname(__file__), "const.py")
    try:
        import const
    except ImportError:
        jsondict = json.load(open(constfilepath))
        with open(constfilepy, 'w') as outf:
            outf.write("json=%s" % jsondict)
        import const
    return const.json

def get_current_time():
    dt = datetime.now()
    return dt.strftime("%Y-%m-%d %X")

def create_menu(frame, data):
    for title, args in data.items():
        m = wx.Menu()
        for arg in args:
            if arg == -1:
                m.AppendSeparator()
            else:
                # kind: 0 normal, 1 check, 2 radio, -1 seprator
                arg["id"] = arg.get('id', -1)
                arg["kind"] = arg.get('kind', 0)
                mi = MenuItem(parentMenu=m, **arg)
                m.AppendItem(mi)
                frame.Bind(wx.EVT_MENU, mi.get_arg("handler"), mi)
                mi.Enable({1: 1, 0: 0, None: 1}[mi.get_arg("enable")])
        yield (m, title)

def create_menubar(frame, data):
    mb = wx.MenuBar()
    # create menu
    for m, title in create_menu(frame, data):
        mb.Append(m, title)
    return mb


@constructor
class MenuItem(wx.MenuItem):
    pass

@constructor
class ReceiveListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    def construct(self):
        listmix.ListCtrlAutoWidthMixin.__init__(self)

    def AddRows(self, data_list):
        # self.DeleteAllColumns()
        self.DeleteAllItems()
        popUpWin = False
        # for pos, heading in enumerate(get_const()["headings"]):
        #     self.InsertColumn(pos, heading, format=wx.LIST_FORMAT_LEFT)
        for key, row in enumerate(data_list):
            count = self.GetItemCount()
            pos = self.InsertStringItem(count, row[0])
            # add values in the other columns on the same row
            for idx, val in enumerate(row[1:]):
                self.SetStringItem(pos, idx + 1, val)
            self.SetItemData(pos, key + 1)
            const_resolveStatus = get_const()["resovle_status"]
            listitem = self.GetItem(pos)

            if row[-1] == const_resolveStatus["closed"]:
                listitem.SetTextColour(wx.NamedColour("GRAY"))
            elif row[-1] == const_resolveStatus["unresolved"]:
                listitem.SetTextColour(wx.NamedColour("RED"))
                listitem.SetFont(listitem.GetFont().Bold())
                # popUpWin = row[2] in get_const()["resource"].values()
                popUpWin = True
            elif row[-1] == const_resolveStatus["resolved"]:
                listitem.SetTextColour(wx.NamedColour("BLUE"))
                listitem.SetFont(listitem.GetFont().Bold())
            self.SetItem(listitem)
        # self.addCache(data_list)
        return popUpWin


    initRows = AddRows

    def AdaptWidth(self, headings_num, proportions):
        num = sum(proportions)
        _w = self.GetSize()[0] / float(num)
        for i in range(headings_num):
            w = _w * proportions[i]
            self.SetColumnWidth(i, w)
@constructor
class Frame(wx.Frame, listmix.ColumnSorterMixin):

    @property
    def const(self):
        return get_const()

    @property
    def columnNum(self):
        return len(self.const["headings"])

    def construct(self):
        self._initListCtrl()
        self._initMenuBar()
        # self._initToolbar()
        self.statusbar = self.CreateStatusBar()
        # ----- layout -----
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.LC, 1, wx.EXPAND|wx.ALL)
        listmix.ColumnSorterMixin.__init__(self, self.columnNum)
        self.SetSizer(sizer)
        # self.Layout()
        # ----------
        self.Bind(EVT_COUNT, self.OnCount)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        self.Center()
        self.SetTitle(self.const["weixin_demo_title"])

    def _initMenuBar(self):
        _OD = OrderedDict()
        const_menubar = self.const["menubar"]
        _OD[const_menubar[0]["title"]] = [
            dict(text=const_menubar[0]["items"][0], handler=self.OnSyncData),
            -1,
            dict(text=const_menubar[0]["items"][1], kind=1, handler=self.OnToggleAutoSync),
            -1,
            dict(text=const_menubar[0]["items"][-1], handler=self.OnQuit),
        ]
        _OD[const_menubar[1]["title"]] = [
            dict(text=const_menubar[1]["items"][0], id=777, kind=1, handler=self.OnSwitchTop),
        ]
        _OD[const_menubar[2]["title"]] = [
            dict(text=const_menubar[2]["items"][0], handler=self.OnClockSet)
        ]

        mb = create_menubar(self, _OD)

        # final
        self.SetMenuBar(mb)

    def _initListCtrl(self):
        const_headings = self.const["headings"]
        self.LC = ReceiveListCtrl(self,
                                  style=wx.LC_REPORT,
                                  headings=const_headings,
                                  # columnFormat=wx.LIST_FORMAT_CENTER,
                                  fgcolor='#f40',
                                  )
        # self.LC.SetAutoLayout(True)

        self.il = wx.ImageList(16, 16)

        # self.idx1 = self.il.Add(images.Smiles.GetBitmap())
        self.sm_up = self.il.Add(images.SmallUpArrow.GetBitmap())
        self.sm_dn = self.il.Add(images.SmallDnArrow.GetBitmap())
        self.LC.SetImageList(self.il, wx.IMAGE_LIST_SMALL)

    def _SyncReceiveList(self, *args, **kwargs):
        event = args[0]
        my = MinYuanClient()
        data = my.getReceiveList(page_size=30)
        if "receiveList" in data:
            rl = data["receiveList"]
            signal = self.LC.AddRows(rl)
            if signal and getattr(event, 'auto', False):
            # ----- 弹窗提醒用户有待分解的记录
                if self.IsIconized():
                    self.Restore()
                m = self.FindItemInMenuBar(menuId=777)
                if not m.IsChecked():
                    m.Check()
                    self.SetWindowStyle(self.GetWindowStyle() | wx.STAY_ON_TOP)
                # self.SetWindowStyle(self.GetWindowStyle() ^ wx.STAY_ON_TOP)
            datamap = {}
            for idx, val in enumerate(rl):
                datamap[idx + 1] = tuple(val)
            self.itemDataMap = datamap

            self.LC.Hide()
            self.LC.AdaptWidth(self.columnNum, [1.5, 3, 1, 2, 0.5, 1, 1])
            self.LC.Show()
            self.statusbar.SetStatusText(self.const["sync_end_msg"] + ' at ' + get_current_time())
        else:
            self.statusbar.SetStatusText('')
            dlg = wx.MessageDialog(self,
                                   self.const["sync_error_msg"],
                                   self.const["sync_error_title"],
                                   wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
    def OnSyncData(self, e):
        self.statusbar.SetStatusText(self.const["sync_start_msg"])
        wx.CallAfter(self._SyncReceiveList, e)

    def _initToolbar(self):
        self.tb = tb = self.CreateToolBar()
        tsize = (24, 24)
        new_bmp = wx.ArtProvider.GetBitmap(wx.ART_NEW, wx.ART_TOOLBAR, tsize)
        open_bmp = wx.ArtProvider.GetBitmap(wx.ART_FILE_OPEN, wx.ART_TOOLBAR, tsize)
        copy_bmp = wx.ArtProvider.GetBitmap(wx.ART_COPY, wx.ART_TOOLBAR, tsize)
        paste_bmp = wx.ArtProvider.GetBitmap(wx.ART_PASTE, wx.ART_TOOLBAR, tsize)

        tb.SetToolBitmapSize(tsize)

        # tb.AddSimpleTool(10, new_bmp, "New", "Long help for 'New'")
        tb.AddLabelTool(10, "New", new_bmp, shortHelp="New", longHelp="Long help for 'New'")
        self.Bind(wx.EVT_TOOL, self.OnSyncData, id=10)
        # self.Bind(wx.EVT_TOOL_RCLICKED, self.OnToolRClick, id=10)

        # tb.AddSimpleTool(20, open_bmp, "Open", "Long help for 'Open'")
        tb.AddLabelTool(20, "Open", open_bmp, shortHelp="Open", longHelp="Long help for 'Open'")
        # self.Bind(wx.EVT_TOOL, self.OnToolClick, id=20)
        # self.Bind(wx.EVT_TOOL_RCLICKED, self.OnToolRClick, id=20)

        tb.AddSeparator()
        tb.AddSimpleTool(30, copy_bmp, "Copy", "Long help for 'Copy'")
        # self.Bind(wx.EVT_TOOL, self.OnToolClick, id=30)
        # self.Bind(wx.EVT_TOOL_RCLICKED, self.OnToolRClick, id=30)

        tb.AddSimpleTool(40, paste_bmp, "Paste", "Long help for 'Paste'")
        # self.Bind(wx.EVT_TOOL, self.OnToolClick, id=40)
        # self.Bind(wx.EVT_TOOL_RCLICKED, self.OnToolRClick, id=40)

        tb.AddSeparator()

        # tool = tb.AddCheckTool(50, images.Tog1.GetBitmap(), shortHelp="Toggle this")
        tool = tb.AddCheckLabelTool(50, "Checkable", images.Tog1.GetBitmap(),
                                    shortHelp="Toggle this")
        # self.Bind(wx.EVT_TOOL, self.OnToolClick, id=50)

        # self.Bind(wx.EVT_TOOL_ENTER, self.OnToolEnter)
        # self.Bind(wx.EVT_TOOL_RCLICKED, self.OnToolRClick)  # Match all
        # self.Bind(wx.EVT_TIMER, self.OnClearSB)

        tb.AddSeparator()
        cbID = wx.NewId()

        tb.AddControl(
            wx.ComboBox(
                tb, cbID, "", choices=["", "This", "is a", "wx.ComboBox"],
                size=(150, -1), style=wx.CB_DROPDOWN
            ))
        # self.Bind(wx.EVT_COMBOBOX, self.OnCombo, id=cbID)

        tb.AddStretchableSpace()
        # search = TestSearchCtrl(tb, size=(150, -1), doSearch=self.DoSearch)
        # tb.AddControl(search)

        # Final thing to do for a toolbar is call the Realize() method. This
        # causes it to render (more or less, that is).
        tb.Realize()

    def OnAdd(self, evt):
        pass

    def OnQuit(self, evt):
        if getattr(self, "syncThd", None) and \
                not self.syncThd.stopped():
            self.syncThd.stop()
        self.Destroy()

    def OnSwitchTop(self, e):
        if e.IsChecked():
            self.SetWindowStyle(self.GetWindowStyle() | wx.STAY_ON_TOP)
        else:
            self.SetWindowStyle(self.GetWindowStyle() ^ wx.STAY_ON_TOP)

    def OnClockSet(self, evt):
        pass

    def GetListCtrl(self):
        return self.LC

    def GetSortImages(self):
        return (self.sm_dn, self.sm_up)

    def OnCount(self, e):
        _, s = e.GetValue()
        print s
        if s % 15 == 0:
            e.auto = True
            self.OnSyncData(e)


    def OnToggleAutoSync(self, e):
        if e.IsChecked():
            thd = CountingThread(self, (1, 1))
            self.syncThd = thd
            thd.start()
        else:
            if not self.syncThd.stopped():
                self.syncThd.stop()
