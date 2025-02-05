"""
----------------------------------------------------------------------------
(C) 2024 by Bastián A.
Centro Para la Instrumentacion Astronomica (CePIA)
Universidad de Concepcion
Version 1.0
----------------------------------------------------------------------------
"""

import sys
from PyQt6 import uic, QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np 
import time 
import pyvisa
from pyvisa import constants
import os
from datetime import datetime
import random   #to testing
import math     #to testing

## INIT PYVISA##
rm = pyvisa.ResourceManager()

#call device connected
#print("Connected VISA resources:")
print(rm.list_resources())

dateFormat = "%d-%m-%y"
hourFormat = "%H:%M:%S"
fileFormat = "%d%m%y"

script_directory = os.path.dirname(os.path.abspath(__file__))
ui_folder = r"\GUI_TEC.ui"
ui_dir = script_directory + ui_folder
data_dir = r"\\"


class Interfaz(QtWidgets.QMainWindow):
    def __init__(self,parent=None):
        super(Interfaz,self).__init__(parent)

        # GUI iniciation #
        self.ui=uic.loadUi(ui_dir, self)
        self.setWindowTitle("CePIA - TEC GUI CHARACTERIZATION")

        # to save data #
        _now = datetime.now()
        _date = _now.strftime(fileFormat)
        _title_date = "TEC_data_" + _date
        self.ui.set_file.setText(_title_date)

        # Method #
        self.hertz_adq = 2         # hz to ADQ
        self.buffer    = 100      # graphic buffer

        # code variables #
        self.rig_dmm = None          # '''''''''''''''''''''''''''' #
        self.rig_sp = None           # to connection PyVISA to SCPI #
        self.ls = None               # '''''''''''''''''''''''''''' #
        self.dmm_state = False       #                         #
        self.sp_state = False        # to return device states #
        self.ls_state = False        #                         #
        self.adq_state = False       #                         #
        self.current = 0
        self.voltage = 0
        self.b_sen = 0
        self.c_sen = 0
        self.d_sen = 0
        self.V = '0'
        self.protec_volt = '0'

        # Graph layout #
        self.layout1=self.ui.verticalLayout_3
        self.PlotWidget1=pg.PlotWidget(name="Plot1", title=u'Temperature vs Time')

        self.PlotWidget1.setLabel('bottom', 'Time', 's')
        self.PlotWidget1.setLabel('left', 'Temperature', '°C')
        self.PlotWidget1.setYRange(0,50)
        self.PlotWidget1.showGrid(x=True, y=True)

        # Widget #
        self.layout1.addWidget(self.PlotWidget1)

        # Vectors #
        self.time_data   = []                       # time data list
        self.temp_h_data = []                       # hot temperature data list
        self.temp_c_data = []                       # cool temperature data list
        self.temp_a_data = []                       # ambient temperature data list
        self.plot1 = self.PlotWidget1.plot(pen='b')
        self.plot2 = self.PlotWidget1.plot(pen='r')
        self.plot3 = self.PlotWidget1.plot(pen='g')

        # button actions #
        self.ui.c_dmm.clicked.connect(self.dmm_connection)
        self.ui.c_sp.clicked.connect(self.sp_connection)
        self.ui.c_ls.clicked.connect(self.ls_connection)
        self.ui.volt_set.clicked.connect(self.voltage_set)
        self.ui.prot_volt_set.clicked.connect(self.volt_prot_set)
        self.ui.adq_btn.clicked.connect(self.adq_type)
        self.ui.adq_btn.setCheckable(True)

        # timer variables #
        self._timer1 = QtCore.QTimer(self)
        self._timer1.timeout.connect(self.dmm_data)
        self._timer1.timeout.connect(self.sp_data)
        self._timer1.timeout.connect(self.ls_data)
        self._timer1.timeout.connect(self.graphic)
        self._timer1.timeout.connect(self.adquisition_method)

        # default values #
        self.ui.curr_m.setText("N/M")
        self.ui.volt_m.setText("N/M")
        self.ui.temp_m.setText("N/M")
        self.ui.temp_m_2.setText("N/M")
        self.ui.temp_m_3.setText("N/M")


#///////////////////////////////////////////////////////////////////////////////////////////////////#
#////////////////////////////////////////      METHODS      ////////////////////////////////////////#
#///////////////////////////////////////////////////////////////////////////////////////////////////#


    def dmm_connection(self):
        dmm_connection = '0'
        if self.ui.c_dmm.isChecked() and not self.dmm_state:
            try:
                self.rig_dmm = rm.open_resource('USB0::0x1AB1::0x0588::DM3R153200585::INSTR')
                dmm_connection = self.rig_dmm.query('*OPC?')
                if dmm_connection.strip() == '1':
                    self.rig_dmm.write("*RST") # Reset the instrument
                    time.sleep(0.2)
                    self.rig_dmm.write(":FUNC:CURR:DC") # Set current DC function
                    time.sleep(1)
                    self.rig_dmm.write(":CURR:DC:RANG 1A") #Set 1A range
                    #self.rig_dmm.write(":MEAS AUTO") # Set automatic measurameter
                    hz_to_ms = int(1000/self.hertz_adq)
                    if not self._timer1.isActive():
                        self._timer1.start(hz_to_ms)
                    self.dmm_state = True
                    print("Digital MultiMeter Connected!")
            except Exception as err:
                print(f'error dmm connection (verifique conexión física): {err}')
        elif not self.ui.c_dmm.isChecked() and self.dmm_state:
            try:
                self.rig_dmm = rm.open_resource('USB0::0x1AB1::0x0588::DM3R153200585::INSTR')
                dmm_connection = self.rig_dmm.query('*OPC?')
                if dmm_connection.strip() == '1':
                    self.rig_dmm.write("*RST")
                    self.rig_dmm.close()
                    self.ui.curr_m.setText("N/A")
                    self.dmm_state = False
                    print("Digital MultiMeter Disconnected!")
            except Exception as e:
                print(f"error dmm desconnection (verifique conexión física): {e}")

    def sp_connection(self):
        if self.ui.c_sp.isChecked() and not self.sp_state:
            sp_connection = '0'
            try:
                self.rig_sp = rm.open_resource('USB0::0x1AB1::0xA4A8::DP9D262000405::INSTR')
                sp_connection = self.rig_sp.query('*OPC?')
                if sp_connection.strip().replace('+','') == '1':
                    self.rig_sp.write("*RST")
                    self.rig_sp.write(":INST CH2")
                    time.sleep(0.4)
                    #self.rig_sp.write(":CURR:PROT:CLE")
                    #self.rig_sp.write(":VOLT {self.V}")
                    self.rig_sp.write(':CURR 2')
                    hz_to_ms = int(1000/self.hertz_adq)
                    if not self._timer1.isActive():
                        self._timer1.start(hz_to_ms)
                    self.sp_state = True
                    print("Supply Power Connected!")
            except Exception as e:
                print(f'Error SP Connection (verifique conexión física): {e}')
        elif not self.ui.c_sp.isChecked() and self.sp_state:
            try:
                self.rig_sp = rm.open_resource('USB0::0x1AB1::0xA4A8::DP9D262000405::INSTR')
                sp_connection = self.rig_sp.query('*OPC?')
                if sp_connection.strip().replace('+','') == '1':
                    zero = 0
                    self.rig_sp.write('*RST')
                    self.rig_sp.write(f':VOLT {zero}')
                    self.rig_sp.write(':OUTP CH2,OFF')
                    self.rig_sp.write("VOLT:PROT:STAT OFF")
                    self.rig_sp.close()
                    self.ui.volt_m.setText("N/A")
                    self.sp_state = False
                    print("Supply Power Disconnected!")
            except Exception as e:
                print(f"Error SP desconnection (verifique conexión física): {e}")

    def ls_connection(self):
        if self.ui.c_ls.isChecked() and not self.ls_state:
            try:
                self.ls = rm.open_resource("COM3", baud_rate=57600, parity=constants.Parity.odd, data_bits=7)
                ls_connection = self.ls.query('*OPC?')
                if ls_connection.strip() == '1':
                    self.ls.write("*RST") # Reset the instrument
                    self.plot1.clear()
                    self.plot2.clear()
                    self.plot3.clear()
                    hz_to_ms = int(1000/self.hertz_adq)
                    self.exec_time = time.time()
                    self.PlotWidget1.getViewBox().enableAutoRange()
                    self.time_data   = []
                    self.temp_h_data = []                       # hot temperature data list
                    self.temp_c_data = []                       # cool temperature data list
                    self.temp_a_data = []
                    if not self._timer1.isActive():
                        self._timer1.start(hz_to_ms)
                    self.ls_state = True
                    print("LakeShore Model 336 Connected!")
            except Exception as e:
                print(f"Error LakeShore Connection (verifique conexión física): {e}")
        elif not self.ui.c_ls.isChecked() and self.ls_state:
            try:
                self.ls = rm.open_resource("COM3", baud_rate=57600, parity=constants.Parity.odd, data_bits=7)
                ls_connection = self.ls.query('*OPC?')
                if ls_connection.strip() == '1':
                    self.ls.close()
                    self.ui.temp_m.setText("N/A")
                    self.ls_state = False
                    print("LakeShore Model 336 Disconnected!")
            except Exception as e:
                print(f"Error LakeShore desconnection (verifique conexión física): {e}")

    def voltage_set(self):
        if self.ui.c_sp.isChecked():
            try:
                self.V = round(float(self.ui.volt_c.text()), 2)
                self.protec_volt = round(float(self.ui.prot_volt.text()),2)
                self.rig_sp.write(":INST CH2")

                if self.V >= self.protec_volt and self.protec_volt == 0:
                    self.rig_sp.write(":VOLT:PROT:STAT OFF")
                    self.rig_sp.write(f':VOLT {self.V}')
                    self.rig_sp.write(":OUTP CH2,ON")

                if self.V <= self.protec_volt and self.protec_volt != 0:
                    self.rig_sp.write(f':VOLT {self.V}')
                    self.rig_sp.write(":OUTP CH2,ON")

                if self.V < self.protec_volt and self.protec_volt == 0:
                    self.rig_sp.write(":VOLT:PROT:STAT ON")
                    self.rig_sp.write(':VOLT {self.V}')
                    self.rig_sp.write(":OUTP CH2,ON")

            except Exception as e:
                print(f"Error in voltage set: {e}")

    def volt_prot_set(self):
        if self.ui.c_sp.isChecked():
            try:
                self.protec_volt = round(float(self.ui.prot_volt.text()), 2)

                if self.protec_volt != 0:
                    self.rig_sp.write(f":VOLT:PROT {self.protec_volt}")
                    self.rig_sp.write(":VOLT:PROT:STAT ON")
                else:
                    self.V = self.protec_volt
                    self.rig_sp.write(':VOLT {self.V}')
                    self.rig_sp.write(":OUTP CH2,ON")
                
            except Exception as e:
                print(f"error in voltage protection set: {e}")
        else:
            #self.ls = rm.open_resource('USB0::0x1AB1::0x0E11::DP8C170700397::INSTR')
            self.rig_sp.write("*RST")
            self.rig_sp.close()

    def dmm_data(self):
        if self.dmm_state:
            try:
                self.rig_dmm.write(':MEASure:CURRent:DC?')
                self.current =  self.rig_dmm.read()
                self.current = self.current.strip()
                self.ui.curr_m.setText(str(self.current))
            except Exception as e:
                print(f'rigol_dmm error (data_reading): {e}')
        elif not self.dmm_state:
            self.ui.curr_m.setText('N/A')
        elif not self.sp_state and not self.dmm_state and not self.sp_state:
            self._timer1.stop()

    def sp_data(self):
        if self.sp_state:
            try:
                self.voltage = self.rig_sp.write(':MEAS:VOLT:DC?')
                self.voltage = self.rig_sp.read()
                self.voltage = self.voltage.strip()
                self.ui.volt_m.setText(self.voltage)
            except Exception as e:
                print(f'rigol_sp error (data_reading): {e}')
        elif not self.sp_state:
            self.ui.volt_m.setText('N/A')
        elif not self.sp_state and not self.dmm_state and not self.sp_state:
            self._timer1.stop()

    def ls_data(self):
        if self.ls_state:
            try:
                self.ls.write('CRDG? B')
                self.b_sen = round(float(self.ls.read()), 3) #random.randint(50,90)
                self.ls.write('CRDG? C')
                self.c_sen = round(float(self.ls.read()), 3) #random.randint(10,40)
                self.d_sen = 'N/A'#float(self.ls.query('CRDG? D')) #or resistance command
                self.ui.temp_m.setText(str(self.b_sen))
                self.ui.temp_m_2.setText(str(self.c_sen))
                self.ui.temp_m_3.setText(str(self.d_sen))  #self.ui.temp_m_3.setText(str(self.T_conv))
                self.current_time = round(time.time() - self.exec_time, 1)
                self.adq_state = True
                #self.t_to_r()
            except Exception as e:
                print(f'lakeshore error (data_reading): {e}')
        elif not self.ls_state:
            self.ui.temp_m.setText('N/A')
            self.ui.temp_m_2.setText('N/A')
            self.ui.temp_m_3.setText('N/A')
        elif not self.ls_state and not self.dmm_state and not self.sp_state:
            self._timer1.stop()


    #def t_to_r(self):

    #    R = float(self.d_sen)
    #    Tk = 1 / (1.167e-3 + (2.267e-4)*math.log(R) + (1.283e-7)*(math.log(R)**3))
    #    self.T_conv = Tk - 273.15
    #    self.ui.temp_m_3.setText(self.T_conv)


    def graphic(self):
        if self.ls_state:
            try:
                self.time_data.append(self.current_time)
                self.temp_h_data.append(self.b_sen)
                self.temp_c_data.append(self.c_sen)
                self.temp_a_data.append('N/A')#self.d_sen) #self.temp_a_data.append(self.T_conv)

                if len(self.time_data) > self.buffer:
                    self.time_data.pop(0)
                    self.temp_h_data.pop(0)
                    self.temp_c_data.pop(0)
                    #self.temp_a_data.pop(0)
                    pass
                
                self.plot1.setData(self.time_data,self.temp_h_data)
                self.plot2.setData(self.time_data,self.temp_c_data)
                #self.plot3.setData(self.time_data,self.temp_a_data)
            except Exception as e:
                print(f"Graphic data error: {e}")


    def adq_type(self):
        if self.ls_state and self.ui.adq_btn.isChecked():
            self.ui.adq_btn.setText('ADQ OFF')
            self.adq_state = True
            print(f"Started saving data:   [ {script_directory} ]")
            print(f"type saving data: <voltage>, <current>, <hot-temperature>, <cool-temperature>, <ambient-temperature>")

        if self.ls_state and not self.ui.adq_btn.isChecked():
            self.ui.adq_btn.setText('ADQ ON')
            self.ui.adq_btn.setChecked(False)
            self.adq_state = False
            print('Stopped saving data')

    def adquisition_method(self):
        if self.adq_state and self.ui.adq_btn.isChecked():
            self.name_file = self.ui.set_file.text()
            with open(f"{script_directory}\\{self.name_file}.csv", "a+") as files:
                try:
                    date_time = datetime.now().strftime(f'{dateFormat}_{hourFormat}')
                    files.write(f"{self.voltage},{self.current},{self.b_sen},{self.c_sen},{self.d_sen},{date_time}\n")
                except Exception as e:
                    print(f"ADQ Error: {e}")


    def closeEvent(self, event):
        self._timer1.stop()

        if self.ui.c_dmm.isChecked():
            self.rig_dmm = rm.open_resource('USB0::0x1AB1::0x0588::DM3R153200585::INSTR')
            self.rig_dmm.write("*RST")
            self.rig_dmm.close()

        if self.ui.c_sp.isChecked():
            self.rig_sp = rm.open_resource('USB0::0x1AB1::0xA4A8::DP9D262000405::INSTR')
            zero = 0
            self.rig_sp.write('*RST')
            self.rig_sp.write(f':VOLT {zero}')
            self.rig_sp.write(f':CURR {zero}')
            self.rig_sp.write(':OUTP CH1,OFF')
            self.rig_sp.write("VOLT:PROT:STAT OFF")
            self.rig_sp.close()

        if self.ui.c_ls.isChecked():
            self.ls = rm.open_resource("COM3", baud_rate=57600, parity=constants.Parity.odd, data_bits=7)
            self.ls.write("*RST")
            self.ls.close()


if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    window = Interfaz()
    window.show()
    sys.exit(app.exec())