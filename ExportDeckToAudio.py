from aqt import mw, utils
from aqt.qt import *
from aqt import editor
from anki import notes
from anki.utils import intTime, ids2str
import platform
import re
from pydub import AudioSegment
from random import shuffle


prog = re.compile("\[sound:(.*?\.(?:mp3|m4a|wav))\]")


def generate_audio(deck_name, num_audios, num_plays, num_copies, default_waiting_time, additional_waiting_time, mode):
    deck = mw.col.decks.byName(deck_name)
    if deck == None:
        utils.showInfo("Deck {} does not exist.".format(deck_name))
    decks = []
    if len(mw.col.decks.children(deck['id'])) == 0:
        decks = [deck_name,]
    else:
        decks = [name for (name, _) in mw.col.decks.children(deck['id'])]
    deck_audios = []
    for name in decks:
        query = 'deck:"{}"'.format(name)
        card_ids = mw.col.findCards(query=query)
        children_audios = [] ## each element of audios is a dict contain audios for front and back card
        for cid in card_ids:
            card = mw.col.getCard(cid)
            card_audios = []
            audio_fields_dict = {}
            audio_fields_list = []
            for field, value in card.note().items():
                match = prog.findall(value)
                if match:
                    audio_fields_dict[field] = []
                    audio_fields_list.append(field)
                    if platform.system() == 'Windows':
                        media_path = mw.col.path.rsplit('\\', 1)[0] + '\\collection.media\\'
                    else:
                        media_path = mw.col.path.rsplit('/', 1)[0] + '/collection.media/'
                    for audio in match:
                        file_path = media_path + audio
                        audio_fields_dict[field].append(file_path)
            
            front_audio_fields, back_audio_fields = split_audio_fields(card, audio_fields_list)

            audio_dict = {}
            audio_dict['front'] = []
            audio_dict['back'] = []
            for faf in front_audio_fields:
                audio_dict['front'].extend(audio_fields_dict[faf])
            for baf in back_audio_fields:
                audio_dict['back'].extend(audio_fields_dict[baf])
            children_audios.append(audio_dict)
        deck_audios.append(children_audios)
    
    combine = AudioSegment.empty()
    audios = []

    if mode == 'Random subdecks':
        shuffle(deck_audios)
        for children_audios in deck_audios:
            shuffle(children_audios)
            for audio in children_audios:
                audios.append(audio)
    else:
        for children_audios in deck_audios:
            for audio in children_audios:
                audios.append(audio)
    if mode == 'Random all':
        shuffle(audios)
    
    for idx in range(0, len(audios), num_audios):
        combine_card_audio = AudioSegment.empty()
        for audio_dict in audios[idx:idx + num_audios]:
            combine_back_audio = AudioSegment.empty()
            if len(audio_dict['back']) > 0:
                for audio_name in audio_dict['back']:
                    tmp_audio = AudioSegment.from_file(audio_name)
                    tmp_audio.set_frame_rate(24000)
                    tmp_audio.set_channels(1)
                    combine_back_audio += tmp_audio
            silence_duration = len(combine_back_audio) if len(combine_back_audio) > 0 else int(default_waiting_time * 1000)
            silence = AudioSegment.silent(duration=silence_duration + int(additional_waiting_time * 1000))
            combine_front_audio = AudioSegment.empty()
            if len(audio_dict['front']) > 0:
                for audio_name in audio_dict['front']:
                    tmp_audio = AudioSegment.from_file(audio_name)
                    tmp_audio.set_frame_rate(24000)
                    tmp_audio.set_channels(1)
                    combine_front_audio += tmp_audio
            combine_card_audio += combine_front_audio + silence + combine_back_audio + silence
        for _ in range(num_plays):
            combine += combine_card_audio

    return combine
    #combine.export("C:\\Users\\Admin\\Desktop\\output.mp3", format="mp3")

def split_audio_fields(card, audio_fields):
    def helper(q):
        q_times = []
        start = 0
        while True:
            s = q.find('{{', start)
            if s == -1: break
            e = q.find('}}', s)
            if e != -1:
                if q[s + 2:e] in audio_fields:
                    q_times.append(q[s + 2:e][:])
                start = e + 2
            else: break
        return q_times

    question_audio_fields = []
    answer_audio_fields = []
    if card is not None:
        m = card.note().model()
        t = m['tmpls'][card.ord]
        q = t.get('qfmt')
        a = t.get('afmt')
        question_audio_fields.extend(helper(q))
        answer_audio_fields.extend(helper(a))
    return question_audio_fields, answer_audio_fields

class AddonDialog(QDialog):

    """Main Options dialog"""
    def __init__(self):
        QDialog.__init__(self, parent=mw)
        self.path = None
        self.deck = None
        self.advance_mode = False
        self._setup_ui()

    def _handle_button(self):
        dialog = OpenFileDialog()
        self.advance_mode = True
        self.path = dialog.filename
        if self.path is not None:
            utils.showInfo("Choose file successful.")

    def _setup_ui(self):
        """Set up widgets and layouts"""
        choose_deck_label = QLabel("Choose deck")
        num_audio_per_group_label = QLabel("Number of audios per groups")
        num_plays_label = QLabel("Number of plays")
        num_copies_label = QLabel("Number of copies")
        default_waiting_label = QLabel("Default waiting time (s)")
        additional_waiting_label = QLabel("Additional waiting time (s)")
        mode_label = QLabel("Mode")

        self.deck_selection = QComboBox()
        self.deck_selection.addItems(sorted(mw.col.decks.allNames()))
        self.num_audios = QLineEdit("6", self)
        self.num_plays = QLineEdit("2", self)
        self.num_copies = QLineEdit("1", self)
        self.default_waiting_time = QLineEdit("3", self)
        self.additional_waiting_time = QLineEdit("0", self)
        self.mode = QComboBox()
        self.mode.addItems(["Overview", "Random all", "Random subdecks"])

        self.advanced_mode_button = QPushButton('Advanced mode')
        self.advanced_mode_button.clicked.connect(self._handle_button)

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(choose_deck_label, 1, 0, 1, 1)
        grid.addWidget(self.deck_selection, 1, 1, 1, 2)
        grid.addWidget(num_audio_per_group_label, 2, 0, 1, 1)
        grid.addWidget(self.num_audios, 2, 1, 1, 2)
        grid.addWidget(num_plays_label, 3, 0, 1, 1)
        grid.addWidget(self.num_plays, 3, 1, 1, 2)
        grid.addWidget(num_copies_label, 4, 0, 1, 1)
        grid.addWidget(self.num_copies, 4, 1, 1, 2)
        grid.addWidget(default_waiting_label, 5, 0, 1, 1)
        grid.addWidget(self.default_waiting_time, 5, 1, 1, 2)
        grid.addWidget(additional_waiting_label, 6, 0, 1, 1)
        grid.addWidget(self.additional_waiting_time, 6, 1, 1, 2)
        grid.addWidget(mode_label, 7, 0, 1, 1)
        grid.addWidget(self.mode, 7, 1, 1, 2)
        grid.addWidget(self.advanced_mode_button, 8, 0, 1, 1)

        # Main button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok
                        | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self._on_reject)

        # Main layout
        l_main = QVBoxLayout()
        l_main.addLayout(grid)
        l_main.addWidget(button_box)
        self.setLayout(l_main)
        self.setMinimumWidth(360)
        self.setWindowTitle('Export deck to audios')

    def _on_accept(self):
        utils.showInfo("Start exporting.")
        combines = []
        names = []
        if self.advance_mode:
            with open(self.path) as f:
                i = 0
                for line in f:
                    if i == 0:
                        i += 1
                        continue
                    deck_name, num_audios, num_plays, num_copies, default_waiting_time, additional_waiting_time, mode, output_name = line.split(',')
                    num_audios = int(num_audios)
                    num_plays = int(num_plays)
                    num_copies = int(num_copies)
                    default_waiting_time = float(default_waiting_time)
                    additional_waiting_time = float(additional_waiting_time)
                    combines.append(generate_audio(deck_name, num_audios, num_plays, num_copies, default_waiting_time, additional_waiting_time, mode))
                    names.append(output_name)
        else:
            ## get values
            deck_name = self.deck_selection.currentText()
            try:
                num_audios = int(self.num_audios.text())
                num_plays = int(self.num_plays.text())
                num_copies = int(self.num_copies.text())
                default_waiting_time = float(self.default_waiting_time.text())
                additional_waiting_time = float(self.additional_waiting_time.text())
            except Exception as e:
                utils.showInfo("You must enter a positive integer.")
                return
            if num_audios <= 0 or num_plays <= 0 or num_copies < 0:
                utils.showInfo("You must enter a positive integer.")
                return
            mode = self.mode.currentText()
            combines.append(generate_audio(deck_name, num_audios, num_plays, num_copies, default_waiting_time, additional_waiting_time, mode))

        if not self.advance_mode:
            combine = combines[0]
            dialog = SaveFileDialog()
            path = dialog.filename
            if path == None:
                return
            combine.export(path)
            utils.showInfo("Export to audio successfully!")
        else:
            if platform.system() == 'Windows':
                init_directory = "C:\\Users\\Admin\\Desktop\\"
            else:
                init_directory = "~/home/"
            directory = str(QFileDialog.getExistingDirectory(self, "Select directory", init_directory, QFileDialog.ShowDirsOnly))
            for name, combine in zip(names, combines):
                name = name.strip()
                if '.mp3' not in name:
                    name += '.mp3'
                if platform.system() == 'Windows':
                    combine.export(directory + '\\' + name.strip())
                else:
                    combine.export(directory + '/' + name)
            utils.showInfo("Export to audio successfully!")


    def _on_reject(self):
        self.close()


class SaveFileDialog(QDialog):

    def __init__(self):
        QDialog.__init__(self, mw)
        self.title='Save File'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480
        self.filename = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.filename = self._get_file()

    def _get_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        if platform.system() == 'Windows':
            directory = "C:\\Users\\Admin\\Desktop"
        else:
            directory = "~/Desktop/"
        try:
            path = QFileDialog.getSaveFileName(self, "Save File", directory, "Audios (*.mp3)", options=options)
            if path:
                return path
            else:
                utils.showInfo("Cannot open this file.")
        except:
            utils.showInfo("Cannot open this file.")
        return None


class OpenFileDialog(QDialog):

    def __init__(self):
        QDialog.__init__(self, mw)
        self.title = 'Open file'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480
        self.filename = None
        self._init_ui()
    

    def _init_ui(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.filename = self._get_file()
        # self.exec_()
    

    def _get_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        if platform.system() == 'Windows':
            directory = "C:\\Users\\Admin\\Desktop"
        else:
            directory = "~/Desktop/"
        try:
            path = QFileDialog.getOpenFileName(self, "Open File", directory, "CSV Files (*.csv)", options=options)
            if path:
                return path
            else:
                utils.showInfo("Cannot open this file.")
        except:
            utils.showInfo("Cannot open this file.")
            return None


class CustomMessageBox(QMessageBox):

    def __init__(self, *__args):
        QMessageBox.__init__(self, parent=mw.app.activeWindow() or mw)
        self.timeout = 0
        self.autoclose = False
        self.currentTime = 0

    def showEvent(self, QShowEvent):
        self.currentTime = 0
        if self.autoclose:
            self.startTimer(1000)

    def timerEvent(self, *args, **kwargs):
        self.currentTime += 1
        if self.currentTime >= self.timeout:
            self.done(0)

    @staticmethod
    def showWithTimeout(timeoutSeconds, message, title, icon=QMessageBox.Information, buttons=QMessageBox.Ok):
        w = CustomMessageBox()
        w.autoclose = True
        w.timeout = timeoutSeconds
        w.setText(message)
        w.setWindowTitle(title)
        w.setIcon(icon)
        sg = w.parent().rect()
        x = sg.width() / 2 - w.pos().x() - w.rect().width()
        y = sg.height() / 2 - w.pos().y() - w.rect().height()
        w.move(x, y)
        w.exec_()


def display_dialog():
    dialog = AddonDialog()
    dialog.exec_()

    
action = QAction("Export deck to audios", mw)
action.triggered.connect(display_dialog)
mw.form.menuTools.addAction(action)