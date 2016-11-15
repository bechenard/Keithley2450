import os,time,datetime
import numpy as np
import visa

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.backend_bases import key_press_handler
from matplotlib.figure import Figure
from scipy.interpolate import interp1d

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column as SQLColumn
from sqlalchemy import Integer as SQLInteger
from sqlalchemy import String as SQLString
from sqlalchemy import Float as SQLFloat
from sqlalchemy import PickleType as SQLPickleType
from sqlalchemy.orm import sessionmaker

USING_PYTHON_3 = False
from sys import version_info
if version_info.major == 2:
    # Python 2
    import Tkinter as tkinter
    import tkFileDialog
elif version_info.major == 3:
    # Python 3
    import tkinter
    USING_PYTHON_3 = True


USE_EMULATION = True

TABLE_NAME  = 'testtable2'
DB_NAME     = 'testdb'
DB_PASSWORD = 'password'

CONNECT_TO_REAL_DB = False
ECHO_SQL_COMMANDS = False






Base = declarative_base()
class Entry(Base):
    __tablename__ = TABLE_NAME
            
    id = SQLColumn(SQLInteger, primary_key=True)

    username    = SQLColumn(SQLString(50))
    sipmid      = SQLColumn(SQLString(50))
    temperature = SQLColumn(SQLFloat)
    date        = SQLColumn(SQLString(50))
    
    v0          = SQLColumn(SQLFloat)
    v1          = SQLColumn(SQLFloat)
    steps       = SQLColumn(SQLInteger)
    deltat      = SQLColumn(SQLFloat)

    varray = SQLColumn(SQLPickleType)
    iarray = SQLColumn(SQLPickleType)
  
    def __repr__(self):
        return "<Entry(id='%s', sipmID='%s', date='%s', user='%s')>" % (self.id, self.sipmid, self.date, self.username)



class data():
    
    def __init__(self):
        self.V           = np.array([0])
        self.I           = np.array([0])
        self.temperature = 20
        self.date        = ""
        self.sipmID    = ""
        self.userName    = ""
        self.hasData     = 0
        
    def read(self, filename, inst):
        try:
            f = open(filename,'r')
            self.sipmID    = f.readline().rstrip('\n')
            self.userName    = f.readline().rstrip('\n')
            self.date        = f.readline().rstrip('\n')
            self.temperature = float(f.readline().rstrip('\n'))
            inst.parV0       = float(f.readline().rstrip('\n'))
            inst.parV1       = float(f.readline().rstrip('\n'))
            inst.parST       = int(f.readline().rstrip('\n'))
            inst.parDT       = float(f.readline().rstrip('\n'))
            #
            npts   = int(f.readline().rstrip('\n'))            
            self.V = np.zeros(npts)
            self.I = np.zeros(npts)
            for i in range(0,npts):
                self.V[i],self.I[i] = map(float,f.readline().split())
            f.close()
            #
            return 1
        except:
            return 0


    def write(self, filename, inst):
        try:
            f = open(filename,'w')
            f.write(self.sipmID+"\n")
            f.write(self.userName+"\n")
            f.write(self.date+"\n")
            f.write(str(self.temperature)+"\n")
            f.write(str(inst.parV0)+"\n")
            f.write(str(inst.parV1)+"\n")
            f.write(str(inst.parST)+"\n")
            f.write(str(inst.parDT)+"\n")            
            f.write(str(self.V.size)+"\n")
            #
            for i in range(0,self.V.size):
                f.write(str(self.V[i])+" "+str(self.I[i])+"\n")
            f.close()
            return 1
        except:
            return 0

class keithley_2450_fake():

    def __init__(self):
        self.name = "Fake Keithley 2450"
        self.logMessage = ''
        self.parV0      = 0
        self.parV1      = 2
        self.parST      = 10
        self.parDT      = 0.01
        self.Vmax       = 10
        self.STmax      = 2000
        self.DTmin      = 0.01
        self.DTmax      = 1
        

    def printDevices(self):
        print("I see the fake device");

    def connect(self):
        self.logMessage = "I am connected to the fake keithley"
        return 1
        
    def disconnect(self):
        pass

    def checkConnection(self):        
        return 1

    def measureIV(self,data):
        data.V = np.linspace(self.parV0,self.parV1,self.parST,1)
        data.I = np.random.uniform(0, 1, size=self.parST)





class keithley_2450():

    def __init__(self):
        self.rm         = visa.ResourceManager()
        self.name       = "Keithler 2450"
        self.USBname    = 'USB0::0x05E6::0x2450::04086751::INSTR'
        self.logMessage = ''
        self.parV0      = 0
        self.parV1      = 2
        self.parST      = 10
        self.parDT      = 0.01
        self.Vmax       = 50
        self.STmax      = 2000
        self.DTmin      = 0.01
        self.DTmax      = 1
        

    # print all devices you can connect to
    def printDevices(self):
        print("I see the following devices:");
        print(self.rm.list_resources())

    #connect to the beloved Keithley
    def connect(self):
        try:
            self.inst = self.rm.open_resource(self.USBname)
            self.logMessage = "I am connected to " + self.inst.query('*IDN?')
            return 1
        except:
            self.logMessage = "Can't connect to device"
            return 0
        
    #disconnect to the apparatus
    def disconnect(self):
        try:
            self.inst.close()
        except:
            pass

    #check we're still connected, pretty sure somebody will pull the cable...
    def checkConnection(self):        
        try:
            self.inst.query('*IDN?')  
        except:
            self.message = "Apparatus disconnected - check connections and power"
            return 0
        return 1


    #finally serious stuff, meaure IV curve
    def measureIV(self,data):

        #prepare the measurement
        buffer="SOUR:SWE:VOLT:LIN %i, %i, %i, %.3f\n" % (self.parV0,self.parV1,self.parST,self.parDT)
        
        self.inst.write("*RST;*CLS\n")
        self.inst.write("SENS:CURR:RANG:AUTO ON\n")
        self.inst.write("SOUR:FUNC VOLT\n")
        self.inst.write("SOUR:VOLT:ILIM 1\n")
        self.inst.write(buffer)
        self.inst.write("INIT\n")
        self.inst.write("*OPC?\n")

        # this checks if the bit set by OPC is 1 amd if we can read the output
        time.sleep(1.1*self.parST*self.parDT)
        readingStat = 0
        while(readingStat==0):
            try:         
                readingStat = int(self.inst.read())        
            except:
                time.sleep(1)

        #retrieve data
        buffer1="TRAC:DATA? 1,%i, \"defbuffer1\",SOUR\n" % (self.parST)
        buffer2="TRAC:DATA? 1,%i, \"defbuffer1\",READ\n" % (self.parST)
        data.V = np.array(self.inst.query_ascii_values(buffer1))
        data.I = np.array(self.inst.query_ascii_values(buffer2))

        self.inst.write("OUTP OFF\n")










class simpleapp_tk(tkinter.Tk):

    def __init__(self,parent):
        tkinter.Tk.__init__(self,parent)

        self.parent   = parent
                
        if USE_EMULATION:
            self.inst     = keithley_2450_fake()
        else:
            self.inst     = keithley_2450()
        self.data     = data()

        col           = self.winfo_rgb(self.cget('bg'))
        self.bgcolor  = (float(col[0])/65536,float(col[1])/65536,float(col[2])/65536)

        self.waitingOnImport = 0

        self.selectWindow = None

        self.ConnectToDB()
        self.initialize()
        
    def initialize(self):
        self.grid()

        #cretae menu bar
        self.menubar = tkinter.Menu(self)
        filemenu = tkinter.Menu(self.menubar, tearoff=0)
        filemenu.add_command(label="Open", command=self.OnMenuOpen)
        filemenu.add_command(label="Save", command=self.OnMenuSave)
        filemenu.add_separator()
        filemenu.add_command(label="Print", command=self.OnMenuPrint)
        filemenu.add_separator()
        filemenu.add_command(label="Quit", command=self.OnMenuQuit)
        self.menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=self.menubar)

        # create the entry boxes
        FrameEntry  = tkinter.Frame(self)
        FrameScan   = tkinter.Frame(FrameEntry)
        FrameDevice = tkinter.Frame(FrameEntry)

        self.CreateScanLabel(FrameScan)
        self.CreateDeviceLabel(FrameDevice)
        
        self.entryVariableV0.set(self.inst.parV0)
        self.entryVariableV1.set(self.inst.parV1)
        self.entryVariableST.set(self.inst.parST)
        self.entryVariableDT.set(self.inst.parDT)
        self.entryVariableUS.set(self.data.userName)
        self.entryVariableSI.set(self.data.sipmID)
        self.entryVariableTE.set(self.data.temperature)
        self.UpdateDate()

        FrameDevice.grid(column=0,row=0,padx=10,pady=20,sticky='EW')
        FrameScan.grid(  column=0,row=1,padx=10,pady=20,sticky='EW')
       
        #create the plotter
        FramePlot = tkinter.Frame(self)
        self.CreatePlotter(FramePlot)

        # create the buttons
        FrameButton = tkinter.Frame(self)
        self.CreateButtons(FrameButton)
        
        # create the logger
        FrameLogger = tkinter.Frame(self)
        self.CreateLogger(FrameLogger)

        #create frame import
        FrameImport = tkinter.Frame(self)
        self.CreateImportList(FrameImport)
        
        #place frames, try to make it look nice
        fillLabel = tkinter.Label(self,text=" ",height=2)
        fillLabel2 = tkinter.Label(self,text=" ",width=20)
        FrameEntry.grid(column=0,row=0,padx=10,pady=10,sticky='EW')
        FramePlot.grid(column=1,row=0,sticky='EW',padx=10,pady=10,rowspan=2)
        fillLabel.grid(column=0,row=1)
        FrameButton.grid(column=0,row=2,sticky='EW',padx=10,pady=10,columnspan=2)
        FrameLogger.grid(column=0,row=3,sticky='EW',padx=10,pady=5,columnspan=2)
        fillLabel2.grid(column=3,row=0)
        FrameImport.grid(column=4,row=0,sticky='EW',padx=10,pady=5,rowspan=4)
 
        self.grid_columnconfigure(0,weight=1)
        self.resizable(False,False)
        self.update()
        self.geometry(self.geometry())       

        

       


        
    #---------------------------------------------------------------------------------
    def OnMenuOpen(self):
        filename = None
        if USING_PYTHON_3:
            filename = tkinter.filedialog.askopenfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("text files","*.txt"),("all files","*.*")))
        else:
            filename =  tkFileDialog.askopenfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("text files","*.txt"),("all files","*.*")))
        if (self.data.read(filename,self.inst)==0):
            self.EmitLogText("Error: Could not read "+filename)
            return

        self.entryVariableV0.set(self.inst.parV0)
        self.entryVariableV1.set(self.inst.parV1)
        self.entryVariableST.set(self.inst.parST)
        self.entryVariableDT.set(self.inst.parDT)
        self.entryVariableSI.set(self.data.sipmID)
        self.entryVariableUS.set(self.data.userName)
        self.entryVariableTE.set(self.data.temperature)
        self.entryVariableDA.set(self.data.date)
        self.data.hasData = 1
        self.RefreshPlot()    
        self.EmitLogText("Loaded content of "+filename)

        
    def OnMenuSave(self):

        self.RefreshParams()
        self.RefreshPlot()
        
        if (self.ValidateSaveData()==0): return        

        filename = None
        if USING_PYTHON_3:
            filename =  tkinter.filedialog.asksaveasfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("text files","*.txt"),("all files","*.*")))
        else:
            filename =  tkFileDialog.asksaveasfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("text files","*.txt"),("all files","*.*")))
        result = self.data.write(filename,self.inst)
        if (result==0):
            self.EmitLogText("Error: Problem saving file "+filename+". Try again")
        self.EmitLogText("Saved into file "+filename)


    def OnMenuPrint(self):
        filename = None
        if USING_PYTHON_3:
            filename = tkinter.filedialog.asksaveasfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("pdf files","*.pdf"),("all files","*.*")))
        else:
            filename = tkFileDialog.asksaveasfilename(initialdir = os.getcwd(),title = "Select file",filetypes = (("pdf files","*.pdf"),("all files","*.*")))
        self.figure.savefig(filename)
        self.EmitLogText("Printed plot into file "+filename)


    def OnMenuQuit(self):
        global app
        self.inst.disconnect()
        app.destroy()



    
    #---------------------------------------------------------------------------------
    def CreateDeviceLabel(self,frame):
        label0 = tkinter.Label(frame, text="Device", font="bold",height=2)
        self.entryVariableTE = tkinter.StringVar()
        self.entryVariableUS = tkinter.StringVar()
        self.entryVariableSI = tkinter.StringVar()
        self.entryVariableDA = tkinter.StringVar()
        
        self.labelUS = tkinter.Label(frame, text="User name")
        self.labelSI = tkinter.Label(frame, text="Device ID")
        self.labelTE = tkinter.Label(frame, text="Temperature [C]")
        self.labelDA = tkinter.Label(frame, text="Date")

        self.entryUS = tkinter.Entry(frame, width = 10,textvariable=self.entryVariableUS)
        self.entrySI = tkinter.Entry(frame, width = 10,textvariable=self.entryVariableSI)
        self.entryTE = tkinter.Entry(frame, width = 10,textvariable=self.entryVariableTE)
        self.entryDA = tkinter.Label(frame, textvariable=self.entryVariableDA)

        label0.grid(column=0,row=0,sticky='W',columnspan=2,)
        self.FinalizeEntryLabel(self.labelUS,self.entryUS,1,self.OnValidateUS)
        self.FinalizeEntryLabel(self.labelSI,self.entrySI,2,self.OnValidateSI)
        self.FinalizeEntryLabel(self.labelTE,self.entryTE,3,self.OnValidateTE)
        self.labelDA.grid(column=0,row=4,sticky='E',padx=5)
        self.entryDA.grid(column=1,row=4,sticky='EW',padx=5)



    def CreateScanLabel(self,frame):
        label0 = tkinter.Label(frame, text="Scan parameters", font="bold",height=2)
        self.entryVariableV0 = tkinter.StringVar()
        self.entryVariableV1 = tkinter.StringVar()
        self.entryVariableST = tkinter.StringVar()
        self.entryVariableDT = tkinter.StringVar()
        self.entryVariableTE = tkinter.StringVar()
        
        self.labelV0 = tkinter.Label(frame, text="V0 [V]")
        self.labelV1 = tkinter.Label(frame, text="V1 [V]")
        self.labelST = tkinter.Label(frame, text="# Step")
        self.labelDT = tkinter.Label(frame, text="dT [s]")

        self.entryV0 = tkinter.Entry(frame, width = 10,textvariable=self.entryVariableV0)
        self.entryV1 = tkinter.Entry(frame, width = 10,textvariable=self.entryVariableV1)
        self.entryST = tkinter.Entry(frame, width = 10,textvariable=self.entryVariableST)
        self.entryDT = tkinter.Entry(frame, width = 10,textvariable=self.entryVariableDT)

        label0.grid(column=0,row=0,sticky='W',columnspan=2)
        self.FinalizeEntryLabel(self.labelV0,self.entryV0,1,self.OnValidateV0)
        self.FinalizeEntryLabel(self.labelV1,self.entryV1,2,self.OnValidateV1)
        self.FinalizeEntryLabel(self.labelST,self.entryST,3,self.OnValidateST)
        self.FinalizeEntryLabel(self.labelDT,self.entryDT,4,self.OnValidateDT)
        
    def FinalizeEntryLabel(self,label,entry,irow,cmd):
        label.grid(column=0,row=irow,sticky='E',padx=5)
        entry.grid(column=1,row=irow,sticky='EW',padx=5)
        entry.bind("<Return>", cmd)

    def OnValidateV0(self, event): 
        #self.inst.parV0 = self.ValidateParInt(self.entryVariableV0, self.inst.parV0, 0, min(self.inst.Vmax,self.inst.parV1), "V0")
        self.inst.parV0 = self.ValidateParFloat(self.entryVariableV0, self.inst.parV0, 0, min(self.inst.Vmax,self.inst.parV1), "V0")

    def OnValidateV1(self, event): 
        #self.inst.parV1 = self.ValidateParInt(self.entryVariableV1, self.inst.parV1, max(0,self.inst.parV0), self.inst.Vmax, "V1")
        self.inst.parV1 = self.ValidateParFloat(self.entryVariableV1, self.inst.parV1, max(0,self.inst.parV0), self.inst.Vmax, "V1")
        
    def OnValidateST(self, event): 
        self.inst.parST = self.ValidateParInt(self.entryVariableST, self.inst.parST, 1, self.inst.STmax, "STEP")

    def OnValidateDT(self, event): 
        self.inst.parDT = self.ValidateParFloat(self.entryVariableDT, self.inst.parDT, self.inst.DTmin, self.inst.DTmax, "DT")
  
    def OnValidateUS(self, event): 
        self.data.userName = self.entryVariableUS.get()
        self.EmitLogText("set user name to "+self.data.userName)

    def OnValidateSI(self, event): 
        self.data.sipmID = self.entryVariableSI.get()
        self.EmitLogText("set device ID to "+self.data.sipmID)

    def OnValidateTE(self, event): 
        self.data.temperature = self.ValidateParFloat(self.entryVariableTE, self.data.temperature, -100.0, 100.0, "Temperature")




        
    #---------------------------------------------------------------------------------
    def CreatePlotter(self,frame):
        self.figure  = Figure(figsize=(5,5), dpi=100,facecolor=self.bgcolor)
        self.figure.subplots_adjust(left=0.2)
        self.figure.subplots_adjust(bottom=0.2)
        self.plotter = self.figure.add_subplot(111)
        self.plotter.plot(self.data.I,self.data.V)
        self.plotter.set_xlabel("V [V]")
        self.plotter.set_ylabel("I [A]")
        self.figure.suptitle("I-V curve for " + self.data.sipmID, fontsize=14, fontweight='bold')
        self.canvasFig = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvasFig.show()
        self.canvasFig.get_tk_widget().grid(column=0,row=2)





    #---------------------------------------------------------------------------------
    def CreateButtons(self,frame):
        self.buttonConnect    = tkinter.Button(frame,text=u"Connect",font='bold',
                                               command=self.OnButtonConnect)       
        self.buttonDisconnect = tkinter.Button(frame,state="disabled",text=u"Disconnect",font='bold',
                                               command=self.OnButtonDisconnect)
        self.buttonMeasure    = tkinter.Button(frame,state="disabled",text=u"Measure",font='bold',
                                               command=self.OnButtonMeasure)

        self.buttonConnect.grid(column=0,row=0,padx=10)
        self.buttonDisconnect.grid(column=1,row=0,padx=10)
        self.buttonMeasure.grid(column=2,row=0,padx=10)

        
    def OnButtonConnect(self):
        if (self.inst.connect()==1):            
            self.label.configure(bg="green")
            self.labelVariable.set("Connected to "+self.inst.name)
            self.buttonConnect.configure(state="disabled")
            self.buttonDisconnect.configure(state="active")
            self.buttonMeasure.configure(state="active")
        self.EmitLogText(self.inst.logMessage)

    def OnButtonDisconnect(self):        
        self.inst.disconnect()
        self.label.configure(bg="red")
        self.labelVariable.set("Disconnected")
        self.buttonConnect.configure(state="active")
        self.buttonDisconnect.configure(state="disabled")
        self.buttonMeasure.configure(state="disabled")
        self.buttonImport.configure(state="disabled")
            
    def OnButtonMeasure(self):
        if (self.inst.checkConnection() == 1):
            self.RefreshParams()
            self.inst.measureIV(self.data)
            self.data.hasData = 1
            self.buttonExport.configure(state="active")
            self.RefreshPlot()
            self.UpdateDate()
        else:
            self.OnButtonDisconnect()
            self.EmitLogText(self.inst.logMessage)





    #---------------------------------------------------------------------------------        
    def CreateImportList(self,frame):
        label0 = tkinter.Label(frame, text="Measurements", font="bold",height=2)       
        label0.grid(column=0,row=0,sticky='W')
                        
        self.scroller2 = tkinter.Scrollbar(frame)
        self.scroller2.grid(column=2,row=1,sticky='ns')        

        self.listImport = tkinter.Listbox(frame,height=25,width=50,yscrollcommand = self.scroller2.set)
        self.scroller.config(command=self.listImport.yview)
        self.listImport.grid(column=0,row=1,sticky='EW')

        FrameButton = tkinter.Frame(frame)

        self.entryVariableFilterSI = tkinter.StringVar()        
        self.entryVariableFilterUS = tkinter.StringVar()        
        self.labelFSI = tkinter.Label(FrameButton, text="Sipm ID filter: ")
        self.labelFUS = tkinter.Label(FrameButton, text="User filter: ")
        self.entryFSI = tkinter.Entry(FrameButton, width = 10,textvariable=self.entryVariableFilterSI)
        self.entryFUS = tkinter.Entry(FrameButton, width = 10,textvariable=self.entryVariableFilterUS)

        self.buttonExport = tkinter.Button(FrameButton,state="disabled",text=u"Export",font='bold',
                                           command=self.OnButtonExport)
        self.buttonImport = tkinter.Button(FrameButton,state="disabled",text=u"Import",font='bold',
                                           command=self.OnButtonImport)
        self.buttonFilter = tkinter.Button(FrameButton,state="disabled",text=u"Filter",font='bold',
                                           command=self.OnButtonFilter)

        self.labelFSI.grid(column=0,row=1,padx=10,pady=20,sticky='EW')
        self.entryFSI.grid(column=1,row=1,padx=10,pady=20,sticky='EW')
        self.labelFUS.grid(column=0,row=2,padx=10,sticky='EW')
        self.entryFUS.grid(column=1,row=2,padx=10,sticky='EW')

        self.buttonImport.grid(column=0,row=0,padx=10,sticky='EW')
        self.buttonExport.grid(column=1,row=0,padx=10,sticky='EW')
        self.buttonFilter.grid(column=2,row=0,padx=10,sticky='EW')
        FrameButton.grid(column=0,row=2,pady=20,sticky='EW')

        self.listImport.bind("<Return>",self.HandleListboxReturnKey)
        
        self.GenerateImportList()

 

    def OnButtonExport(self):
        self.RefreshParams()
        self.RefreshPlot()
        valid = self.ValidateSaveData()

        if valid==0:
            self.EmitLogText("ERROR: Cannot export data (Missing data)")
            return

        if self.connectedToDB==0:
            self.EmitLogText("ERROR: Cannot export data (Not connected to database)")
            return
       
        self.EmitLogText('Exporting data to DB')
        self.WriteEntry()

        
    def OnButtonImport(self):
        if self.waitingOnImport != 0:
            self.EmitLogText("ERROR: Already waiting for import selection")
            return 0

        if self.connectedToDB!=1:
            self.EmitLogText("ERROR: Cannot import data (Not connected to database)")
            return 0

        if (self.listImport.curselection()):
            self.ImportSingleEntry(self.listImport.get(self.listImport.curselection()))


    def OnButtonFilter(self):
        importSipmID = self.entryVariableFilterSI.get()
        importUser   = self.entryVariableFilterUS.get()
        self.GenerateImportList(importSipmID,importUser)


    def HandleListboxReturnKey(self, event):
        if(self.buttonImport.cget("state")=="active"):
            self.buttonImport.invoke()
           
 
    def GenerateImportList(self,importSipmID="",importUser=""):
        self.listImport.delete(0,tkinter.END)
        
        try:
            session = self.Session()

            if (importSipmID == "" and importUser == ""):
                importList = session.query(Entry).all()
            if (importSipmID != "" and importUser != ""):
                importList = session.query(Entry).filter_by(sipmid=importSipmID,username=importUser)
            if (importSipmID == "" and importUser != ""):
                importList = session.query(Entry).filter_by(username=importUser)
            if (importSipmID != "" and importUser == ""):
                importList = session.query(Entry).filter_by(sipmid=importSipmID)

            entryNum = 1
            for curEntry in importList:
                self.listImport.insert(entryNum, curEntry.date+" | "+curEntry.sipmid+" | "+curEntry.username)
                entryNum += 1
                
            self.buttonImport.configure(state="disabled")
            if (entryNum>1):
                self.listImport.select_set(0)
                self.buttonImport.configure(state="active")
                self.buttonFilter.configure(state="active")
            
        except:
            session.rollback()
            self.EmitLogText("ERROR: Communication problem with SQL database")
            raise

        finally:
            session.close()  



    def ImportSingleEntry(self, selectionString):
        importDate   = selectionString.split("|")[0].strip()
        importSipmID = selectionString.split("|")[1].strip()

        if self.connectedToDB!=1:
            self.EmitLogText("ERROR: Cannot import data (Not connected to database)")
            return 0

        try:
            session = self.Session()

            our_entry = session.query(Entry).filter_by(sipmid=importSipmID,date=importDate).first()
    
            if our_entry==None:
                self.EmitLogText("ERROR: Cannot import data (Entry not found)")
                return 0
        
            self.data.userName    = our_entry.username
            self.data.sipmID      = our_entry.sipmid
            self.data.temperature = our_entry.temperature
            self.data.date        = our_entry.date
            self.inst.parV0       = our_entry.v0
            self.inst.parV1       = our_entry.v1
            self.inst.parST       = our_entry.steps
            self.inst.parDT       = our_entry.deltat
            self.data.V           = our_entry.varray
            self.data.I           = our_entry.iarray

            self.entryVariableV0.set(self.inst.parV0)
            self.entryVariableV1.set(self.inst.parV1)
            self.entryVariableST.set(self.inst.parST)
            self.entryVariableDT.set(self.inst.parDT)
            self.entryVariableSI.set(self.data.sipmID)
            self.entryVariableUS.set(self.data.userName)
            self.entryVariableTE.set(self.data.temperature)
            self.entryVariableDA.set(self.data.date)
            self.data.hasData = 1
            self.RefreshPlot()    
            self.EmitLogText('Successfully imported device \"'+self.data.sipmID+'\" from DB' )
            
        except:
            session.rollback()
            self.EmitLogText("ERROR: Communication problem with SQL database")
            raise
        finally:
            session.close()  

        return


    def WriteEntry(self):
        try:
            session = self.Session()
            
            query_entry = session.query(Entry).filter_by(sipmid=self.data.sipmID,date=self.data.date).first()
            if query_entry!=None:
                self.EmitLogText("Replacing existing entry...")
                session.delete(query_entry)
                session.commit()
            
            new_entry = Entry(username    = str(self.data.userName),
                              sipmid      = str(self.data.sipmID),
                              temperature = float(self.data.temperature),
                              date        = str(self.data.date),
                              v0          = float(self.inst.parV0),
                              v1          = float(self.inst.parV1),
                              steps       = int(self.inst.parST),
                              deltat      = float(self.inst.parDT),
                              varray      = self.data.V,
                              iarray      = self.data.I)

            session.add(new_entry)
            session.commit()
            
            our_entry = session.query(Entry).filter_by(sipmid=self.data.sipmID).first()
            if our_entry==None:
                self.EmitLogText("ERROR: Could not export to DB")
                return 0
            
            self.EmitLogText("New Entry: "+our_entry.__repr__())

            entries = session.query(Entry).all()
            self.EmitLogText("Number of entries in DB: "+str(len(entries)))
            self.GenerateImportList()

        except:
            session.rollback()
            self.EmitLogText("ERROR: Could not export to DB")
            raise
        finally:
            session.close()
            return 1


    #---------------------------------------------------------------------------------
    def CreateLogger(self,frame):                                 
        self.labelVariable = tkinter.StringVar()
        self.labelColor    = tkinter.StringVar()
        self.labelColor.set("red")
        self.labelVariable.set(u"Not connected")        
        self.label = tkinter.Label(frame, textvariable=self.labelVariable,
                                   anchor="w",fg="white",bg=self.labelColor.get())
        self.label.grid(column=0,row=0,sticky='EW',pady=5)

        self.scroller = tkinter.Scrollbar(frame)
        self.scroller.grid(column=2,row=1,sticky='ns')        
        self.logtext = tkinter.Text(frame,height=5,yscrollcommand = self.scroller.set)
        self.scroller.config(command=self.logtext.yview)
        self.logtext.insert(tkinter.INSERT, "Good day\n")
        self.logtext.configure(state="disabled")
        self.logtext.grid(column=0,row=1,sticky='EW')





                     



    #---------------------------------------------------------------------------------
    def ConnectToDB(self):

        self.engine = None
        self.Session = None
        self.connectedToDB = 0

        try:
            if CONNECT_TO_REAL_DB:
                pw = DB_PASSWORD
                self.engine = create_engine('mysql+mysqldb://root:'+pw+'@localhost/'+DB_NAME+'?unix_socket=//opt/local/var/run/mysql56/mysqld.sock', echo=ECHO_SQL_COMMANDS)
            else:
                self.engine = create_engine('sqlite:///:memory:', echo=ECHO_SQL_COMMANDS)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
            self.connectedToDB = 1
            print("Connected to DB")
            return 1
        except:
            return 0



    def UpdateDate(self):
        now = datetime.datetime.now()
        self.data.date = "%s-%s-%s %s:%s:%s" % (now.year,now.month,now.day,now.hour,now.minute,now.second)
        self.entryVariableDA.set(self.data.date)
       
    def RefreshParams(self):
        self.inst.parV0       = float( self.entryVariableV0.get() )
        self.inst.parV1       = float( self.entryVariableV1.get() )
        self.inst.parST       = int(   self.entryVariableST.get() )
        self.inst.parDT       = float( self.entryVariableDT.get() )
        self.data.sipmID      =        self.entryVariableSI.get()
        self.data.userName    =        self.entryVariableUS.get()
        self.data.temperature = float( self.entryVariableTE.get() )

    def RefreshPlot(self):
        self.plotter.clear()
        self.finterp = interp1d(self.data.V,self.data.I, kind='cubic')
        xnew = np.linspace(self.data.V[0], self.data.V[-1], num=max(self.inst.parST,100), endpoint=True)
        self.plotter.plot(self.data.V,self.data.I,'o',xnew,self.finterp(xnew),'-')
        #self.plotter.plot(self.data.V,self.data.I)
        self.plotter.set_xlabel("V [V]")
        self.plotter.set_ylabel("I [A]")
        self.figure.suptitle("I-V curve for " + self.data.sipmID, fontsize=14, fontweight='bold')
        
        self.canvasFig.draw()


    def EmitLogText(self, text):
        self.logtext.config(state='normal')
        self.logtext.insert(tkinter.END, text + "\n")
        self.logtext.see(tkinter.END)
        self.logtext.config(state='disabled')
        


    def ValidateParInt(self, entryVar, oldPar, bound0, bound1, parName): 
        try:
            par = int(entryVar.get())
            if (par < bound0 or par > bound1): raise ValueError
            self.EmitLogText("set "+parName+" to " + str(par))
            return par

        except ValueError:             
            self.EmitLogText("Error: "+ parName+" must be in the range "+str(bound0)+"....."+str(bound1))
            entryVar.set(oldPar)
            return oldPar

    def ValidateParFloat(self, entryVar, oldPar, bound0, bound1, parName): 
        try:
            par = float(entryVar.get())
            if (par < bound0 or par > bound1): raise ValueError
            self.EmitLogText("set "+parName+" to " + str(par))
            return par

        except ValueError:             
            self.EmitLogText("Error: "+parName+" must be in the range "+str(bound0)+".."+str(bound1))
            entryVar.set(oldPar)
            return oldPar

 
    def ValidateSaveData(self):
        if (self.data.userName == ""): 
            self.EmitLogText("Error: Username missing, so we know who to blame later...")
            return 0
        
        if (self.data.sipmID == ""): 
            self.EmitLogText("Error: device ID missing")
            return 0

        if (self.data.hasData==0): 
            self.EmitLogText("Error: No measurement available")
            return 0

        return 1







        
          
if __name__ == "__main__":
    app = simpleapp_tk(None)
    app.title('IV curve measurement')
    app.mainloop()





