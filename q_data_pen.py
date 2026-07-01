import os
from qgis.core import QgsMapLayerType, QgsWkbTypes, Qgis, NULL, QgsMessageLog
from qgis.gui import QgsMapToolIdentify
from qgis.PyQt.QtWidgets import QAction, QDialog, QVBoxLayout, QComboBox, QLineEdit, QPushButton, QLabel
from qgis.PyQt.QtGui import QIcon, QPixmap,QCursor
from qgis.PyQt.QtCore import Qt, QLocale




# 1. Das Dialog-Fenster (Eingabemaske)
class QuickEditDialog(QDialog):
    
    def __init__(self, fields, feat, last_field=None, parent=None):
        super().__init__(parent)
        self.feat = feat  # Hier wird das Polygon gespeichert
        
        self.setWindowTitle("Q-Data-Pen")
        self.resize(300, 170)
        self.layout = QVBoxLayout(self)

        # Dropdown
        self.layout.addWidget(QLabel("Select attribute:"))
        self.combo = QComboBox()
        self.combo.addItems(fields)
        if last_field and last_field in fields:
            self.combo.setCurrentText(last_field)
        self.layout.addWidget(self.combo)

        # Anzeige-Label für den aktuellen Wert
        self.current_value_label = QLabel("Current Value: ")
        font = self.current_value_label.font()
        font.setBold(True)
        self.current_value_label.setFont(font)
        self.layout.addWidget(self.current_value_label)

        # Eingabefeld für den neuen Wert
        self.layout.addWidget(QLabel("New value:"))
        self.input = QLineEdit()
        self.layout.addWidget(self.input)

        # Button
        self.btn = QPushButton("OK")
        self.btn.clicked.connect(self.accept)
        self.layout.addWidget(self.btn)

        # Signale verknüpfen und initial ausführen
        self.combo.currentTextChanged.connect(self.update_display)
        self.update_display(self.combo.currentText())

    def update_display(self, field_name):
        if field_name:
            # Den aktuellen Wert aus dem Feature auslesen
            val = self.feat.attribute(field_name)
            
            # Anzeige aktualisieren
            if val == NULL or val is None:
                self.current_value_label.setText("Current Value: NULL (empty)")
            else:
                self.current_value_label.setText(f"Current Value: {val}")

            # Eingabefeld bei jedem Wechsel leeren
            self.input.clear()

    def get_data(self):
        return self.combo.currentText(), self.input.text()


# 2. Das Klick-Werkzeug
class PolygonClickTool(QgsMapToolIdentify):
    
    def __init__(self, canvas, iface):
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface
        self.last_field = None
        pathcursor = os.path.join(os.path.dirname(__file__), 'cursor.png')
        pixmap = QPixmap(pathcursor)
        pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio)
        self.setCursor(QCursor(pixmap))

    def canvasReleaseEvent(self, event):
        layer = self.canvas.currentLayer()

        if not layer or layer.type() != QgsMapLayerType.VectorLayer:
            self.iface.messageBar().pushMessage("Please select a vector layer.", Qgis.Info, 3)
            return

        if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            self.iface.messageBar().pushMessage("Only polygon layers are supported.", Qgis.Info, 3)
            return

        if not layer.isEditable():
            layer.startEditing()
            self.iface.messageBar().pushMessage("Q-Data-Pen: Edit mode has been activated.", Qgis.Success, 3)
  
        results = self.identify(event.x(), event.y(), [layer], QgsMapToolIdentify.TopDownStopAtFirst)

        if results:
            feat = results[0].mFeature
            fields = [f.name() for f in layer.fields()]

            # Dialog aufrufen (feat wird übergeben!)
            dlg = QuickEditDialog(fields, feat, self.last_field, self.iface.mainWindow())
            
            if dlg.exec_():
                field_name, val = dlg.get_data()
                self.last_field = field_name
                
                # Nur speichern, wenn auch wirklich etwas in das leere Feld eingetippt wurde
                if val.strip() != "":
                    field_idx = layer.fields().lookupField(field_name)
                    layer.changeAttributeValue(feat.id(), field_idx, val)
                    self.canvas.refresh()



# 3. Die Plugin-Klasse
class QDataPen:
    
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.tool = None
        self.toolbar = None 

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        if not os.path.exists(icon_path):
            icon = QIcon(":/images/themes/default/mActionIdentify.svg")
        else:
            icon = QIcon(icon_path)
        self.action = QAction(icon, "Q-Data-Pen activate", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.run)
        self.iface.mapCanvas().mapToolSet.connect(self.tool_changed)

        self.iface.addToolBarIcon(self.action)
        
        self.iface.addPluginToMenu("&Q-Data-Pen", self.action)

    def unload(self):
        self.iface.removePluginMenu("&Q-Data-Pen", self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.tool:
            self.iface.mapCanvas().unsetMapTool(self.tool)

    def tool_changed(self, tool):
        if tool != self.tool and self.action.isChecked():
            self.action.setChecked(False)

    def run(self, checked):
        canvas = self.iface.mapCanvas()
        if checked:
            if not self.tool:
                self.tool = PolygonClickTool(canvas, self.iface)
            canvas.setMapTool(self.tool)
        else:
            canvas.unsetMapTool(self.tool)