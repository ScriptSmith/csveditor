import sys
import csv
from collections import OrderedDict
from time import sleep

from PyQt5 import QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from mainwindow import Ui_MainWindow

emit_inc = 1000


class CSVEditor(Ui_MainWindow):
    def __init__(self, window):
        super().__init__()
        self.setupUi(window)
        window.show()

        self.statusbar.hide()
        self.page.setEnabled(False)
        window.setWindowIcon(QIcon('ui/icon.png'))

        self.actionQuit.triggered.connect(QtWidgets.qApp.quit)
        self.actionOpen_csv.triggered.connect(self.open_file)
        self.actionSave_csv.triggered.connect(self.save_file)
        self.actionAbout.triggered.connect(self.about_stack)
        self.doneButton.clicked.connect(self.home_stack)
        self.addButton.clicked.connect(self.add_fields)
        self.removeButton.clicked.connect(self.remove_fields)

        self.read_thread = None
        self.write_thread = None

        self.old_file = None
        self.old_file_name = None

    @staticmethod
    def error_message(exception,
                      text="An error occurred when processing your request",
                      title="Error"):

        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setText(text)
        msg.setWindowTitle(title)
        msg.setDetailedText(str(exception))
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def wait(self):
        if self.write_thread:
            while not self.write_thread.isFinished():
                sleep(1)
                self.write_thread.quit()
        if self.read_thread:
            while not self.read_thread.isFinished():
                sleep(1)
                self.read_thread.quit()

    def open_file(self):
        file_type = "csv"

        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(
            caption="Open", directory="",
            filter="{} Files (*.{});;All Files (*)".format(
                file_type.upper(), file_type),
            options=options)

        if file_name:
            self.old_file_name = file_name
            self.page.setEnabled(True)
            self.page.setToolTip("")
            self.fileNameLabel.setText("File: " + file_name)
            self.read_original_file()

    def save_file(self):
        file_type = "csv"
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            caption="Save", directory="",
            filter="{} Files (*.{});;All Files (*)".format(
                file_type.upper(), file_type),
            options=options)

        if file_name:
            if '.' not in file_name and file_name[-4:] != '.' + file_type:
                file_name += '.' + file_type

            self.write_file(file_name)

    def write_file(self, new_file_name):
        field_names = []
        for index in range(self.newList.count()):
            field_names.append(self.newList.item(index).text())

        self.wait()

        self.write_thread = WriteFile(self.old_file_name, new_file_name,
                                      field_names, self.newRowCount.value())
        self.newRowCount.setValue(0)
        self.write_thread.new_row_set.connect(self.new_row_set)
        self.write_thread.exception.connect(self.error_message)
        self.write_thread.start()

    def home_stack(self):
        self.stackedWidget.setCurrentIndex(0)

    def about_stack(self):
        self.stackedWidget.setCurrentIndex(1)

    def read_original_file(self):
        try:
            with open(self.old_file_name, "r") as f:
                reader = csv.DictReader(f)

                self.originalRowCount.setValue(0)
                self.originalList.clear()
                self.newList.clear()
                self.newRowCount.setValue(0)
                self.originalList.addItems(reader.fieldnames)

            self.wait()

            self.read_thread = UpdateRowCount(self.old_file_name)
            self.read_thread.original_row_set.connect(self.original_row_set)
            self.read_thread.update_new_row.connect(self.update_new_row)
            self.read_thread.exception.connect(self.error_message)
            self.read_thread.start()
        except Exception as e:
            self.error_message(e)

    def add_fields(self):
        current_items = []
        for i in range(self.newList.count()):
            current_items.append(self.newList.item(i).text())

        for item in self.originalList.selectedItems():
            if item.text() not in current_items:
                self.newList.addItem(item.text())
        self.originalList.clearSelection()

    def remove_fields(self):
        for row in self.newList.selectedItems():
            self.newList.takeItem(self.newList.row(row))

    def original_row_set(self, value):
        self.originalRowCount.setValue(value)

    def new_row_set(self, value):
        self.newRowCount.setValue(value)

    def update_new_row(self):
        self.newRowCount.setValue(self.originalRowCount.value())


class UpdateRowCount(QThread):
    original_row_set = pyqtSignal(int)
    update_new_row = pyqtSignal()
    exception = pyqtSignal(Exception)

    def __init__(self, file_name):
        super().__init__()

        self.file_name = file_name

    def run(self):
        read_count = 0

        try:
            with open(self.file_name, 'r') as f:
                reader = csv.reader(f)

                next(reader)
                for row in reader:
                    read_count += 1
                    if read_count % emit_inc == 0:
                        self.original_row_set.emit(read_count)
            self.original_row_set.emit(read_count)
            self.update_new_row.emit()
        except Exception as e:
            self.exception.emit(e)


class WriteFile(QThread):
    new_row_set = pyqtSignal(int)
    exception = pyqtSignal(Exception)

    def __init__(self, old_file, new_file, fields, count):
        super().__init__()

        self.old_file_name = old_file
        self.new_file_name = new_file
        self.fields = fields
        self.count = count

    def run(self):
        written_count = 0

        try:
            if self.new_file_name == self.old_file_name:
                raise FileExistsError("Can't overwrite files. Give the new "
                                      "file a different name")
            with open(self.new_file_name, 'w', encoding='utf-8') as new_file:
                writer = csv.DictWriter(new_file, fieldnames=self.fields)
                writer.writeheader()

                with open(self.old_file_name, 'r') as old_file:
                    reader = csv.DictReader(old_file)

                    for row in reader:
                        if written_count == self.count:
                            break

                        new_row = OrderedDict()
                        for field in self.fields:
                            new_row[field] = row[field]
                        writer.writerow(new_row)
                        written_count += 1
                        if written_count % emit_inc == 0:
                            self.new_row_set.emit(written_count)
            self.new_row_set.emit(written_count)
        except Exception as e:
            self.exception.emit(e)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()
    ui = CSVEditor(main_window)
    sys.exit(app.exec_())
