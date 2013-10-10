import Tkinter
import ttk

class App:
    def __init__(self, master):
        self.root = master
        self.frame = ttk.Frame(self.root, style='TFrame')
        self.frame.pack(fill='both', expand='yes')

        self.b1 =  ttk.Button(self.root, text='unpack')
        self.b1.pack()

        self.b2 = ttk.Button(self.root, text='pack')
        self.b2.pack()


        self.b1.bind('<Button-1>', lambda e, widget=self:unpack(widget))
        self.b2.bind('<Button-1>', lambda e, widget=self:pack(widget))

def pack(widget):
    widget.frame.pack(fill='both', expand='yes')
    print (widget.frame.pack_info())

def unpack(widget):
    widget.frame.pack_forget()



master = Tkinter.Tk()
master.geometry('640x480')
s = ttk.Style()
s.configure('TFrame', background='blue')
app = App(master)
master.mainloop()