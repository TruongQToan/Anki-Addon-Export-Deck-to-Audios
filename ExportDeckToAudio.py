from aqt import mw, utils
from aqt.qt import *
from aqt import editor
from anki import notes
from anki.utils import intTime, ids2str
import platform
import re
from pydub import AudioSegment
from random import shuffle
from os.path import expanduser, join
import unicodedata


prog = re.compile("\[sound:(.*?\.(?:mp3|m4a|wav))\]")
channel_map = {'Stereo': 2, 'Mono': 1}
practice_modes = ["Glossika practice: get the first audio in back card", 
            "Glossika practice: get all audios in back card",
            "Listening practice: get the first audio in back card",
            "Listening practice: get all audios in back card"]


def group_audios(audios, num_plays, num_audios, overview=False):
    grouping_audios = [audios[idx:idx + num_audios] for idx in range(0, len(audios), num_audios)]
    shuffle_audios = []
    for i in range(len(grouping_audios)):
        for _ in range(num_plays):
            if not overview:
                shuffle(grouping_audios[i])
            shuffle_audios.extend(grouping_audios[i])
    
    if not overview:
        for i in range((num_plays - 1) * num_audios, 
            len(shuffle_audios), num_audios * num_plays):
            tmp = shuffle_audios[i:i+2*num_audios]
            shuffle(tmp)
            shuffle_audios[i:i+2*num_audios] = tmp
    
    return shuffle_audios


def combine_audios(audios,
        channel,
        default_waiting_time,
        change_channel,
        additional_waiting_time,
        practice_mode):
    combine = AudioSegment.empty()
    for audio_dict in audios:
        combine_back_audio = AudioSegment.empty()
        if len(audio_dict['back']) > 0:
            if practice_mode == 0 or practice_mode == 2:
                audio_names = audio_dict['back'][:1]
            else:
                audio_names = audio_dict['back']
            for audio_name in audio_names:
                tmp_audio = AudioSegment.from_file(audio_name)
                if change_channel:
                    tmp_audio = tmp_audio.set_channels(int(channel))
                combine_back_audio += tmp_audio
        if practice_mode == 2 or practice_mode == 3:
            silence_duration = int(default_waiting_time) * 1000
        else:
            silence_duration = len(combine_back_audio) if len(combine_back_audio) > 0 else int(default_waiting_time * 1000)
            silence_duration += int(additional_waiting_time * 1000)
        silence = AudioSegment.silent(duration=silence_duration)
        combine_front_audio = AudioSegment.empty()
        if len(audio_dict['front']) > 0:
            for audio_name in audio_dict['front']:
                tmp_audio = AudioSegment.from_file(audio_name)
                if change_channel:
                    tmp_audio = tmp_audio.set_channels(int(channel))
                combine_front_audio += tmp_audio
        combine += combine_front_audio + silence + combine_back_audio + silence
    return combine


def generate_audio(deck_name, 
        num_audios, 
        num_plays, 
        num_copies, 
        default_waiting_time, 
        additional_waiting_time, 
        mode, 
        change_channel,
        channel,
        practice_mode=0):
    if isinstance(deck_name, str):
        deck_name = unicode(deck_name)
    deck_name = deck_name.replace('"', '')
    deck_name = unicodedata.normalize('NFC', deck_name)
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
    
    combines = []

    if mode == 'Random subdecks':
        for _ in range(num_copies):
            audios = []
            shuffle(deck_audios)
            for children_audios in deck_audios:
                shuffle(children_audios)
                for audio in children_audios:
                    audios.append(audio)
            audios = group_audios(audios, num_plays, num_audios)
            combines.append(combine_audios(audios,
                    channel,
                    default_waiting_time,
                    change_channel,
                    additional_waiting_time,
                    practice_mode))
    else:
        for _ in range(num_copies):
            audios = []
            for children_audios in deck_audios:
                for audio in children_audios:
                    audios.append(audio)
            if mode == 'Random all':
                shuffle(audios)
                audios = group_audios(audios, num_plays, num_audios)
            elif mode == 'Overview':
                audios = group_audios(audios, num_plays, num_audios, overview=True)
            combines.append(combine_audios(audios,
                    channel,
                    default_waiting_time,
                    change_channel,
                    additional_waiting_time,
                    practice_mode))
    return combines


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
        self.change_channel = False
        self._setup_ui()

    def _handle_button(self):
        dialog = OpenFileDialog()
        self.advance_mode = True
        self.path = dialog.filename
        if self.path is not None:
            utils.showInfo("Choose file successful.")
        self.csv_file_label.setText(self.path)

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
        decks_list = sorted(mw.col.decks.allNames())
        current_deck = mw.col.decks.current()['name']
        decks_list.insert(0, current_deck)
        self.deck_selection.addItems(decks_list)
        self.num_audios = QLineEdit("7", self)
        self.num_plays = QLineEdit("4", self)
        self.num_copies = QLineEdit("1", self)
        self.default_waiting_time = QLineEdit("3", self)
        self.additional_waiting_time = QLineEdit("0.4", self)
        self.sample_rate = QLineEdit("22050", self)
        self.channel = QComboBox()
        self.channel.addItems(["Mono", "Stereo"])
        self.mode = QComboBox()
        self.mode.addItems(["Overview", "Random all", "Random subdecks"])
        self.practice_mode = QComboBox()
        self.practice_mode.addItems(practice_modes)

        self.advanced_mode_button = QPushButton('Advanced mode')
        self.advanced_mode_button.clicked.connect(self._handle_button)

        self.change_channel_cb = QCheckBox("Export stereo")
        self.change_channel_cb.toggled.connect(self._handle_cb_toggle_cn)

        self.csv_file_label = QLabel("")

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
        grid.addWidget(QLabel("Practice mode"), 8, 0, 1, 1)
        grid.addWidget(self.practice_mode, 8, 1, 1, 1)
        grid.addWidget(self.change_channel_cb, 9, 0, 1, 1)
        grid.addWidget(self.channel, 9, 1, 1, 1)

        self.sample_rate.hide()
        self.channel.hide()

        grid.addWidget(self.advanced_mode_button, 10, 0, 1, 1)
        grid.addWidget(self.csv_file_label, 10, 1, 1, 1)

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

    def _handle_cb_toggle_cn(self):
        if self.change_channel:
            self.change_channel = False
            self.channel.clear()
            self.channel.addItems(["Mono", "Stereo"])
            self.channel.hide()
        else:
            self.change_channel = True
            self.channel.show()


    def _on_accept(self):

        path = None
        directory = None

        if not self.advance_mode:
            dialog = SaveFileDialog(self.deck_selection.currentText().replace("::", "_"))
            path = dialog.filename
            if path == None:
                return
        else:
            init_directory = expanduser("~/Desktop")
            directory = str(QFileDialog.getExistingDirectory(self, "Select directory to save outputs", init_directory, QFileDialog.ShowDirsOnly))

        CustomMessageBox.showWithTimeout(1, "Start exporting", "Notification", icon=QMessageBox.Information, buttons=QMessageBox.Ok)
        combines = []
        names = []
        num_cps = []
        if self.advance_mode:
            with open(self.path) as f:
                i = 0
                for line in f:
                    if i == 0:
                        i += 1
                        continue
                    splitted_fields = line.split(',')
                    deck_name = splitted_fields[0]
                    num_audios = int(splitted_fields[1].strip())
                    num_plays = int(splitted_fields[2].strip())
                    num_copies = int(splitted_fields[3].strip())
                    default_waiting_time = float(splitted_fields[4].strip())
                    additional_waiting_time = float(splitted_fields[5].strip())
                    mode = splitted_fields[6].strip()
                    output_name = splitted_fields[7].strip()
                    channel = channel_map[self.channel.currentText()]
                    combines = generate_audio(deck_name, 
                        num_audios, 
                        num_plays, 
                        num_copies, 
                        default_waiting_time, 
                        additional_waiting_time, 
                        mode, 
                        self.change_channel,
                        channel)
                    if '.mp3' not in output_name:
                        output_name += '.mp3'
                    if num_copies == 1:
                        combine = combines[0]
                        if platform.system() == 'Windows':
                            combine.export(directory + '\\' + output_name, format='mp3', parameters=['-ac', str(channel)])
                        else:
                            combine.export(directory + '/' + output_name, format='mp3', parameters=['-ac', str(channel)])
                    else:
                        for i in range(num_copies):
                            combine = combines[i]
                            new_name = output_name[:-4] + "-" + str(i + 1) + ".mp3"
                            if platform.system() == 'Windows':
                                combine.export(directory + '\\' + new_name, format='mp3', parameters=['-ac', str(channel)])
                            else:
                                combine.export(directory + '/' + new_name, format='mp3', parameters=['-ac', str(channel)])
                utils.showInfo("Export to audio successfully!")
                self.advance_mode = False
                self.csv_file_label.setText('')
        else:
            ## get values
            deck_name = self.deck_selection.currentText()
            try:
                num_audios = int(self.num_audios.text().strip())
                num_plays = int(self.num_plays.text().strip())
                num_copies = int(self.num_copies.text().strip())
                default_waiting_time = float(self.default_waiting_time.text().strip())
                additional_waiting_time = float(self.additional_waiting_time.text().strip())
                _ = int(self.sample_rate.text().strip())
            except Exception as e:
                utils.showInfo("You must enter a positive integer.")
                return
            if num_audios <= 0 or num_plays <= 0 or num_copies < 0:
                utils.showInfo("You must enter a positive integer.")
                return
            mode = self.mode.currentText()
            channel = channel_map[self.channel.currentText()]
            practice_mode = practice_modes.index(self.practice_mode.currentText())
            combines = generate_audio(deck_name, 
                num_audios, 
                num_plays, 
                num_copies, 
                default_waiting_time, 
                additional_waiting_time, 
                mode, 
                self.change_channel,
                channel,
                practice_mode)
            if len(combines) > 0:
                path = path.replace("::", "_")
                if num_copies == 1:
                    combines[0].export(path, format='mp3', parameters=['-ac', str(channel)])
                else:
                    for i in range(num_copies):
                        combine = combines[i]
                        new_path = path[:-4] + "-" + str(i + 1) + ".mp3"
                        combine.export(new_path, format='mp3', parameters=['-ac', str(channel)])
                utils.showInfo("Export to audios successfully!")
            else:
                utils.showInfo("Cannot export to audios.")


    def _on_reject(self):
        self.close()


class SaveFileDialog(QDialog):

    def __init__(self, deck_name):
        QDialog.__init__(self, mw)
        self.title='Save File'
        self.left = 10
        self.top = 10
        self.width = 640
        self.height = 480
        self.filename = None
        self.deck_name = deck_name
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)
        self.filename = self._get_file()

    def _get_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        directory = join(expanduser("~/Desktop"), self.deck_name + '.mp3')
        try:
            path = QFileDialog.getSaveFileName(self, "Save File", directory, "Audios (*.mp3)", options=options)
            if path:
                return path
            if path[-3:] != 'mp3':
                path += '.mp3'
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
        directory = expanduser("~/Desktop")
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
        sg = QDesktopWidget().screenGeometry()
        x = sg.width() / 2 - w.pos().x() - w.rect().width()
        y = sg.height() / 2 - w.pos().y() - w.rect().height()
        w.move(x, y)
        w.exec_()


def display_dialog():
    dialog = AddonDialog()
    dialog.exec_()

    
action = QAction("Export deck to audios", mw)
action.setShortcut("Ctrl+A")
action.triggered.connect(display_dialog)
mw.form.menuTools.addAction(action)