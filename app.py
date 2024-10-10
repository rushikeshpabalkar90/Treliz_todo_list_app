from pprint import pprint

from flask import Flask, render_template, request, redirect, url_for, abort, flash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy

import requests

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

from functools import wraps

from flask_ckeditor import CKEditor
from sqlalchemy import desc
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import make_transient

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import os

import random
from datetime import datetime

all_colors = os.listdir('static/assets/images/board_background_img/bg_colors/')
# all_images = os.listdir("static/assets/images/board_background_img/bg_images/")
all_images = []

Access_key = os.environ['UNSPLASH_ACCESS_KEY']

headers = {
    'Authorization': f'Client-ID {Access_key}'
}

parameters = {
    'query': 'nature',
    'orientation': 'landscape',
    'count': 12
}
unsplash_url = 'https://api.unsplash.com/photos/random/'

try:
    response = requests.get(unsplash_url, headers=headers, params=parameters)
    for i in range(len(response.json())):
        all_images.append(response.json()[i]["urls"]["regular"] + '&w=1920')
except requests.exceptions.ConnectionError:
    pass



logo_colors = ['#CADBC0', '#2F0A28', '#E1DD8F', '#E0777D', '#477890',
               '#E56B70', '#339989', '#FB8824', '#E63946', '#4F345A']

otp_send = False
otp_confirmed = False
OTP = ''
user_forgot_email = ''

current_workspace_id = None
app = Flask(__name__)

app.config['CKEDITOR_SERVE_LOCAL'] = True
app.config['CKEDITOR_PKG_TYPE'] = 'basic'
ckeditor = CKEditor(app)

# postgresql://{user-name}:{password}@{host}:{port-id}/{database-name}

# Secret key for flashes messages
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATION'] = False
db = SQLAlchemy(app)

# global variable for directory to upload files
app.config['CARD_ATTACHMENTS'] = 'static/all_uploads/card_attachments/'
app.config['CARD_COVER_IMAGE'] = 'static/all_uploads/card_cover_image/'
# we should use MAX_CONTENT_LENGTH
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # 8 Megabytes
app.config['ALLOWED_EXTENSIONS_COVER_IMG'] = ['.jpg', '.jpeg', '.png', '.gif']
app.config['ALLOWED_EXTENSIONS_CARD_ATTACHMENT'] = ['.jpg', '.jpeg', '.png', '.gif', '.docx', '.pdf', '.html', '.txt']

login_manager = LoginManager()
login_manager.init_app(app)
app.app_context().push()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Databases

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_name = db.Column(db.String(50), nullable=False)
    user_email = db.Column(db.String(50), unique=True, nullable=False)
    user_password = db.Column(db.String(200), nullable=False)
    user_logo_color = db.Column(db.String(50), nullable=False)

    user_workspaces = relationship("Workspace", back_populates="workspace_creator")
    user_boards = relationship("Board", back_populates="board_creator")
    user_lists = relationship("List", back_populates="list_creator")
    user_cards = relationship("Card", back_populates="card_creator")
    user_attachments = relationship("Attachment", back_populates="attachment_creator")
    user_items = relationship("ChecklistItem", back_populates="item_creator")

    def __repr__(self):
        return f'<User {self.user_name}>'


class Workspace(db.Model):
    __tablename__ = "workspaces"
    workspace_id = db.Column(db.Integer, primary_key=True, nullable=False)
    workspace_name = db.Column(db.String(50), nullable=False)
    workspace_description = db.Column(db.String(250), nullable=True)
    workspace_visibility = db.Column(db.String(50), nullable=True, default='private')
    workspace_logo_color = db.Column(db.String(50), nullable=False)

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    workspace_creator = relationship("User", back_populates="user_workspaces")

    workspace_boards = relationship("Board", back_populates="parent_workspace")

    def __repr__(self):
        return f'<Workspace {self.workspace_name}>'


class Board(db.Model):
    __tablename__ = "boards"
    board_id = db.Column(db.Integer, primary_key=True, nullable=False)
    board_name = db.Column(db.String(50), nullable=False)
    board_visibility = db.Column(db.String(50), nullable=False, default='workspace')
    board_background_image = db.Column(db.String(200), nullable=False)
    board_recent_open_time = db.Column(db.DateTime, nullable=True)
    board_favorite = db.Column(db.Boolean, nullable=False, default=False)
    board_added_date = db.Column(db.DateTime, nullable=False)
    is_template = db.Column(db.Boolean, default=False, nullable=False)

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    board_creator = relationship("User", back_populates="user_boards")

    parent_workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.workspace_id'), nullable=False)
    parent_workspace = relationship("Workspace", back_populates="workspace_boards")

    board_lists = relationship("List", back_populates="parent_board")

    def __repr__(self):
        return f'<Board {self.board_name}>'


class List(db.Model):
    __tablename__ = "lists"
    list_id = db.Column(db.Integer, primary_key=True, nullable=False)
    list_name = db.Column(db.String(50), nullable=False)
    list_position = db.Column(db.Integer, nullable=False)

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    list_creator = relationship("User", back_populates="user_lists")

    parent_board_id = db.Column(db.Integer, db.ForeignKey('boards.board_id'), nullable=False)
    parent_board = relationship("Board", back_populates="board_lists")

    list_cards = relationship("Card", back_populates="parent_list")

    def __repr__(self):
        return f'<List {self.list_name}>'


class Card(db.Model):
    __tablename__ = "cards"
    card_id = db.Column(db.Integer, primary_key=True, nullable=False)
    card_name = db.Column(db.String(50), nullable=False)
    card_position = db.Column(db.Integer, nullable=False)
    card_description = db.Column(db.String(250), nullable=True)
    card_dueDate = db.Column(db.Date(), nullable=True)
    card_checklist_name = db.Column(db.String(50), nullable=True)
    card_cover = db.Column(db.String(200), nullable=True)

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    card_creator = relationship("User", back_populates="user_cards")

    parent_list_id = db.Column(db.Integer, db.ForeignKey('lists.list_id'), nullable=False)
    parent_list = relationship("List", back_populates="list_cards")

    card_attachments = relationship("Attachment", back_populates="parent_card")
    card_checklist_items = relationship("ChecklistItem", back_populates="parent_card")

    def __repr__(self):
        return f'<Card {self.card_name}>'


class Attachment(db.Model):
    __tablename__ = "attachments"
    attachment_id = db.Column(db.Integer, primary_key=True, nullable=False)
    attachment_name = db.Column(db.String(300), nullable=False)
    attachment_extension = db.Column(db.String(50), nullable=False)
    attachment_upload_date = db.Column(db.DateTime(), nullable=False)
    attachment_path = db.Column(db.String(350), nullable=False)
    is_cover_image = db.Column(db.Boolean, nullable=False, default=False)

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    attachment_creator = relationship("User", back_populates="user_attachments")

    parent_card_id = db.Column(db.Integer, db.ForeignKey('cards.card_id'), nullable=False)
    parent_card = relationship("Card", back_populates="card_attachments")

    def __repr__(self):
        return f'<Attachment {self.attachment_name}>'


class ChecklistItem(db.Model):
    __tablename__ = "checklist_items"
    item_id = db.Column(db.Integer, primary_key=True, nullable=False)
    item_name = db.Column(db.String(50), nullable=False)
    item_status = db.Column(db.Boolean, nullable=False)

    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    item_creator = relationship("User", back_populates="user_items")

    parent_card_id = db.Column(db.Integer, db.ForeignKey('cards.card_id'), nullable=False)
    parent_card = relationship("Card", back_populates="card_checklist_items")

    def __repr__(self):
        return f'<ChecklistItem {self.item_name}>'


db.create_all()


# decorator function
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)

    return decorated_function


tasks = ['apple', 'banana', 'watermelon', 'grapes']


def generate_otp():
    # letters_low = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
    #                'u', 'v', 'w', 'x', 'y', 'z']
    numbers = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

    # letters_up = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
    #               'U', 'V', 'W', 'X', 'Y', 'Z']

    # up_letters_list = [random.choice(letters_low) for _ in range(2)]
    # low_letters_list = [random.choice(letters_up) for _ in range(2)]
    numbers_list = [random.choice(numbers) for _ in range(6)]

    # otp_letters = up_letters_list + numbers_list + low_letters_list
    otp_email = "".join(numbers_list)
    return otp_email


def send_otp(email):
    global OTP
    sender = os.environ['ADMIN_EMAIL']
    receivers = email
    password = 'nxpiqeokbgstwged'
    # (generated by App Password in google security settings)
    OTP = generate_otp()

    content = f"To authenticate, please use the following One Time Password(OTP):\n {OTP}\n Don't" \
              f" share this OTP with anyone. Our customer service team will never ask you for your" \
              f" password, OTP, credit card, or banking info.\n We hope to see you again soon."

    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = receivers
    message["Subject"] = 'Reset your password from Treliz'

    message.attach(MIMEText(content, "plain"))

    session = smtplib.SMTP("smtp.gmail.com", 587)
    session.starttls()
    session.login(sender, password)
    text = message.as_string()
    session.sendmail(sender, receivers, text)
    session.quit()


@app.route('/', methods=['GET', 'POST'])
def index_page():
    if request.method == "POST":
        return render_template('signup_page.html', email=request.form['index_email'])
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    if request.method == 'POST':
        if User.query.filter_by(user_email=request.form['Email']).first():
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login_page'))

        elif request.form['Password'] != request.form['Re-Password']:
            flash('Password entries must be same.')

        else:
            hash_and_salted_password = generate_password_hash(request.form['Password'], method='pbkdf2:sha256',
                                                              salt_length=8)

            new_user = User()
            new_user.user_name = request.form['Name']
            new_user.user_email = request.form['Email']
            new_user.user_password = hash_and_salted_password
            new_user.user_logo_color = random.choice(logo_colors)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login_page'))

    return render_template('signup_page.html')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        user = User.query.filter_by(user_email=request.form['Email']).first()

        if user is None:
            flash("You don't have an account, create a free account.")

        elif not check_password_hash(password=request.form['Password'], pwhash=user.user_password):
            flash('Password is incorrect!')

        else:
            login_user(user)
            return redirect(url_for('boards_manager'))

    return render_template('login_page.html')


@app.route('/logout', methods=['POST', 'GET'])
@login_required
def logout_page():
    if request.method == 'POST':
        if 'logout_user' in request.form:
            logout_user()
            return redirect(url_for('index_page'))

    return render_template('logout_page.html', user=current_user)


@app.route('/reset_password', methods=['POST', 'GET'])
def reset_password():
    global otp_send, otp_confirmed, OTP, user_forgot_email
    if request.method == 'POST':

        if 'send_otp' in request.form:
            user = User.query.filter_by(user_email=request.form['Email']).first()
            if user is None:
                flash('email is not registered.')

            else:
                send_otp(request.form['Email'])
                otp_send = True
                user_forgot_email = request.form['Email']

        elif 'reset_password' in request.form:
            if OTP != request.form['OTP']:
                flash('wrong otp entered.')
            else:
                otp_send = False
                otp_confirmed = True

        elif 'change_password' in request.form:
            if request.form['New_Password'] != request.form['Confirm_Password']:
                flash('Password entries must be same.')

            else:
                user = User.query.filter_by(user_email=user_forgot_email).first()
                user.user_password = generate_password_hash(request.form['New_Password'], method='pbkdf2:sha256',
                                                            salt_length=8)
                db.session.commit()
                otp_confirmed = False
                return redirect(url_for('login_page'))

    return render_template('reset_password.html', email=user_forgot_email, otp_send=otp_send,
                           otp_confirmed=otp_confirmed)


@app.route('/boards_manager', methods=['GET', 'POST'])
# @login_required
def boards_manager():
    if len(Workspace.query.all()) == 0 and current_user.id == 1:
        template_workspace = Workspace()
        template_workspace.workspace_name = "Template"
        template_workspace.creator_id = 1
        template_workspace.workspace_logo_color = "grey"
        template_workspace.workspace_description = "This is Template Workspace containing templates."
        db.session.add(template_workspace)
        db.session.commit()

        return redirect(url_for('boards_manager'))

    random.shuffle(all_colors)
    random.shuffle(all_images)
    all_workspaces = Workspace.query.filter_by(creator_id=current_user.id).order_by(Workspace.workspace_id).all()

    if request.method == 'POST':
        if 'create-workspace' in request.form:
            new_workspace = Workspace()
            new_workspace.workspace_name = request.form['Workspace_Name']
            new_workspace.workspace_description = request.form['Workspace_Description']
            new_workspace.creator_id = current_user.id
            new_workspace.workspace_logo_color = random.choice(logo_colors)
            db.session.add(new_workspace)
            db.session.commit()

        if 'create_board' in request.form:
            new_board = Board()
            new_board.board_name = request.form['Board_Name']
            new_board.board_visibility = request.form['Board_Visibility']
            new_board.board_background_image = request.form['boardBackgroundOption']
            new_board.board_added_date = datetime.now()
            new_board.creator_id = current_user.id
            if current_user.id == 1 and len(all_workspaces) <= 2:
                new_board.parent_workspace_id = int(all_workspaces[1].workspace_id)
            elif current_user.id != 1 and len(all_workspaces) <= 1:
                new_board.parent_workspace_id = int(all_workspaces[0].workspace_id)
            else:
                new_board.parent_workspace_id = int(request.form['Board_Workspace'])
            db.session.add(new_board)
            db.session.commit()

        if 'create_template' in request.form:
            new_template = Board()
            new_template.board_name = request.form['Template_Name']
            new_template.is_template = True
            new_template.board_background_image = request.form['templateBgOption']
            new_template.board_added_date = datetime.now()
            new_template.parent_workspace_id = 1
            new_template.creator_id = current_user.id
            db.session.add(new_template)
            db.session.commit()

        if 'edit-workspace' in request.form:
            workspace_to_edit = Workspace.query.filter_by(creator_id=current_user.id,
                                                          workspace_id=request.form['Workspace_Id']).first()
            workspace_to_edit.workspace_name = request.form['Workspace_Name']
            workspace_to_edit.workspace_description = request.form['Workspace_Description']
            db.session.commit()

        if 'delete_workspace' in request.form:
            workspace_to_delete = Workspace.query.filter_by(creator_id=current_user.id,
                                                            workspace_id=int(request.form['Workspace_ID'])).first()
            db.session.delete(workspace_to_delete)
            db.session.commit()

        if 'delete_board' in request.form:
            print(request.form)
            board_to_delete = Board.query.filter_by(board_id=request.form['Board_Id']).first()
            db.session.delete(board_to_delete)
            db.session.commit()

        return redirect(url_for('boards_manager'))

    all_boards_recent = (Board.query.filter_by(creator_id=current_user.id, is_template=False)
                         .order_by(desc(Board.board_recent_open_time)).all())

    all_boards_added = Board.query.filter_by(creator_id=current_user.id, is_template=False).order_by(
        desc(Board.board_added_date)).all()
    all_templates = Board.query.filter_by(is_template=True).all()

    return render_template('boards_manager.html', all_workspaces=all_workspaces, user=current_user,
                           all_colors=all_colors, all_images=all_images, all_boards_recent=all_boards_recent,
                           all_boards=all_boards_added, current_workspace_id=current_workspace_id,
                           all_templates=all_templates)


def clone_agent(id_, updated_name):
    s = db.session
    agent = s.query(List).get(id_)
    child = None
    c = None
    mc1 = None
    mc2 = None

    for i in range(len(agent.list_cards)):
        if agent.list_cards:
            c = agent.list_cards[i]

            child = s.query(Card).get(c.card_id)

            for j in range(len(child.card_attachments)):
                if child.card_attachments:
                    mc1 = child.card_attachments[j]
                    # db.session.expunge does
                    s.expunge(mc1)

                    make_transient(mc1)
                    mc1.attachment_id = None

            for k in range(len(child.card_checklist_items)):
                if child.card_checklist_items:
                    mc2 = child.card_checklist_items[k]
                    # db.session.expunge does
                    s.expunge(mc2)

                    make_transient(mc2)
                    mc2.item_id = None

            # db.session.expunge does
            s.expunge(c)
            make_transient(c)
            c.card_id = None

    s.expunge(agent)
    agent.list_id = None
    agent.list_name = updated_name
    agent.list_position = agent.list_position + 1

    make_transient(agent)
    s.add(agent)
    s.commit()

    if c:
        assert agent.list_id
        c.agent_id = agent.list_id
        s.add(c)
        s.commit()

    if mc1:
        assert child.card_id
        mc1.child_id = child.card_id
        s.add(mc1)
        s.commit()

    if mc2:
        assert child.card_id
        mc2.child_id = child.card_id
        s.add(mc2)
        s.commit()


def clone_card(card_id, updated_name, updated_position, updated_parent_id):
    s = db.session
    agent = s.query(Card).get(card_id)
    c1 = None
    c2 = None

    # card_checklist_items
    for i in range(len(agent.card_attachments)):
        if agent.card_attachments:
            c1 = agent.card_attachments[i]
            s.expunge(c1)
            make_transient(c1)
            c1.attachment_id = None

    for i in range(len(agent.card_checklist_items)):
        if agent.card_checklist_items:
            c2 = agent.card_checklist_items[i]
            s.expunge(c2)
            make_transient(c2)
            c2.item_id = None

    s.expunge(agent)
    agent.card_id = None
    agent.card_name = updated_name
    agent.card_position = updated_position
    agent.parent_list_id = updated_parent_id

    make_transient(agent)

    s.add(agent)
    s.commit()

    if c1:
        assert agent.card_id
        c1.agent_id = agent.card_id
        s.add(c1)
        s.commit()

    if c2:
        assert agent.card_id
        c2.agent_id = agent.card_id
        s.add(c2)
        s.commit()


def increase_or_decrease_position(current_position, destination_position, parent_id):
    if current_position < destination_position:
        # increase position
        for i in range(int(current_position) + 1,
                       int(destination_position) + 1):
            list_to_edit = List.query.filter_by(list_position=i, parent_board_id=parent_id).first()
            list_to_edit.list_position = i - 1
            db.session.commit()

    elif current_position > destination_position:
        # decrease position
        for i in range(-(int(current_position) - 1),
                       -(int(destination_position) - 1)):
            # 4, 3, 2
            i *= -1
            list_to_edit = List.query.filter_by(list_position=i, parent_board_id=parent_id).first()
            list_to_edit.list_position = i + 1
            db.session.commit()


def move_cards_down(from_position, to_position, parent_list_id):
    for i in range(from_position, to_position):
        i *= -1
        card_to_edit = Card.query.filter_by(card_position=i, parent_list_id=parent_list_id).first()
        card_to_edit.card_position = i + 1
        db.session.commit()


def move_cards_up(from_position, to_position, parent_list_id):
    for i in range(from_position, to_position):
        card_to_edit = Card.query.filter_by(card_position=i, parent_list_id=parent_list_id).first()

        card_to_edit.card_position = i - 1
        db.session.commit()


@app.route('/board/<int:board_id>', methods=["POST", "GET"])
@login_required
def board(board_id):
    global current_workspace_id
    one_board = Board.query.get(board_id)
    one_board.board_recent_open_time = datetime.now()
    db.session.commit()

    all_lists = List.query.filter_by(creator_id=current_user.id).order_by(List.list_position).all()
    all_cards = Card.query.filter_by(creator_id=current_user.id).order_by(Card.parent_list_id, Card.card_position).all()
    all_boards = Board.query.filter_by(creator_id=current_user.id, is_template=False)
    all_attachments = Attachment.query.filter_by(creator_id=current_user.id).order_by(
        Attachment.attachment_upload_date).all()
    current_workspace_id = one_board.parent_workspace_id

    if request.method == 'POST':
        if 'add_list' in request.form:
            new_list = List()
            new_list.list_name = request.form['List_Name']
            # start list position with 1 for every new board
            lists_in_board = List.query.filter_by(parent_board_id=board_id)
            new_list.list_position = lists_in_board.count() + 1
            new_list.parent_board_id = board_id
            new_list.creator_id = current_user.id
            db.session.add(new_list)
            db.session.commit()
            return redirect(url_for('board', board_id=board_id))

        if 'add_card' in request.form:
            new_card = Card()
            new_card.parent_list_id = request.form['List_Id']
            new_card.card_name = request.form['Card_Name']
            # give position for each list
            # start position with 1 for every new list
            cards_in_list = Card.query.filter_by(parent_list_id=request.form['List_Id'])
            new_card.card_position = cards_in_list.count() + 1
            new_card.creator_id = current_user.id
            db.session.add(new_card)
            db.session.commit()
            return redirect(url_for('board', board_id=board_id))

        if 'list_name_edit_form' in request.form:
            list_to_edit = List.query.get(request.form['List_Id'])
            list_to_edit.list_name = request.form['List_Name_Edit']
            db.session.commit()
            return redirect(url_for('board', board_id=board_id))

        if 'board_name_edit_form' in request.form:
            board_to_edit = Board.query.get(board_id)
            board_to_edit.board_name = request.form['Board_Name_Edit']
            db.session.commit()
            return redirect(url_for('board', board_id=board_id))

        if 'change_board_bg' in request.form:
            one_board.board_background_image = request.form['boardBgOption']
            db.session.commit()
            return redirect(url_for('board', board_id=board_id))

        if 'favorite_btn' in request.form:
            one_board.board_favorite = not one_board.board_favorite
            db.session.commit()
            return redirect(url_for('board', board_id=board_id))

        if 'move_list_form' in request.form:

            if (request.form['Current_List_Position'] != request.form['Dest_Position_Move_List'] and
                    int(request.form['Dest_Board_Move_List']) == board_id):

                x = 10000

                current_list = List.query.filter_by(list_position=request.form['Current_List_Position'],
                                                    parent_board_id=board_id).first()
                current_list.list_position = x
                db.session.commit()

                increase_or_decrease_position(request.form['Current_List_Position'],
                                              request.form['Dest_Position_Move_List'], board_id)

                destination_list = List.query.filter_by(list_position=x, parent_board_id=board_id).first()
                destination_list.list_position = int(request.form['Dest_Position_Move_List'])
                db.session.commit()

            elif int(request.form['Dest_Board_Move_List']) != board_id:

                # get the current list position and board_id and change its position to destination and board id to
                # destination board in destination board increase all position greater than destination position by one.
                current_list = List.query.filter_by(list_position=request.form['Current_List_Position'],
                                                    parent_board_id=board_id).first()

                x = 10000
                current_list.list_position = x
                current_list.parent_board_id = int(request.form['Dest_Board_Move_List'])
                db.session.commit()

                all_lists_in_current_board = List.query.filter_by(parent_board_id=board_id)
                for i in range(int(request.form['Current_List_Position']) + 1,
                               int(all_lists_in_current_board.count()) + 2):
                    list_to_edit = List.query.filter_by(list_position=i, parent_board_id=board_id).first()
                    # 3, 4, 5
                    list_to_edit.list_position = i - 1
                    db.session.commit()

                all_lists_in_destination_board = List.query.filter_by(
                    parent_board_id=int(request.form['Dest_Board_Move_List']))

                for i in range(-(int(all_lists_in_destination_board.count()) - 1),
                               -(int(request.form['Dest_Position_Move_List']) - 1)):
                    i *= -1

                    list_to_edit = List.query.filter_by(list_position=i,
                                                        parent_board_id=int(
                                                            request.form['Dest_Board_Move_List'])).first()
                    list_to_edit.list_position = i + 1
                    db.session.commit()

                destination_list = List.query.filter_by(list_position=x,
                                                        parent_board_id=int(
                                                            request.form['Dest_Board_Move_List'])).first()
                destination_list.list_position = request.form['Dest_Position_Move_List']
                db.session.commit()

            return redirect(url_for('board', board_id=board_id))

        if 'copy_list_form' in request.form:

            list_to_copy = List.query.filter_by(list_id=int(request.form['Current_List_Id']),
                                                parent_board_id=board_id).first()

            all_lists_in_destination_board = List.query.filter_by(parent_board_id=board_id)

            for i in range(-(int(all_lists_in_destination_board.count())),
                           -(int(request.form['Current_List_Position']))):
                i *= -1

                list_to_edit = List.query.filter_by(list_position=i, parent_board_id=board_id).first()
                list_to_edit.list_position = i + 1
                db.session.commit()

            clone_agent(list_to_copy.list_id, request.form['List_Name_Copy'])

            return redirect(url_for('board', board_id=board_id))

        if 'delete_list_form' in request.form:

            all_cards_in_current_list = Card.query.filter_by(parent_list_id=request.form['Current_List_Id'])

            for card_to_delete in all_cards_in_current_list:

                items_to_delete = ChecklistItem.query.filter_by(parent_card_id=card_to_delete.card_id)
                attachments_to_delete = Attachment.query.filter_by(is_cover_image=False,
                                                                   parent_card_id=card_to_delete.card_id)
                cover_image_attachment = Attachment.query.filter_by(is_cover_image=True,
                                                                    parent_card_id=card_to_delete.card_id).first()

                if attachments_to_delete:
                    for attachment in attachments_to_delete:
                        os.remove(os.path.join(app.config['CARD_ATTACHMENTS'], attachment.attachment_name))
                        db.session.delete(attachment)

                    db.session.commit()

                if cover_image_attachment:
                    os.remove(os.path.join(app.config['CARD_COVER_IMAGE'], cover_image_attachment.attachment_name))

                if items_to_delete:
                    for i in items_to_delete:
                        db.session.delete(i)
                    db.session.commit()

                db.session.delete(card_to_delete)
                db.session.commit()

            list_to_delete = List.query.filter_by(parent_board_id=board_id,
                                                  list_id=request.form['Current_List_Id']).first()
            db.session.delete(list_to_delete)
            db.session.commit()

            return redirect(url_for('board', board_id=board_id))

    return render_template('board.html', all_boards=all_boards, one_board=one_board, all_lists=all_lists,
                           all_cards=all_cards, all_attachments=all_attachments, all_colors=all_colors,
                           all_images=all_images, current_workspace_id=current_workspace_id)


@app.route('/card/<int:id_>/<int:card_id>', methods=['GET', 'POST'])
def card(id_, card_id):
    random.shuffle(all_colors)
    random.shuffle(all_images)
    all_items = ChecklistItem.query.filter_by(creator_id=current_user.id).order_by(ChecklistItem.item_id).all()
    all_lists = List.query.filter_by(creator_id=current_user.id).order_by(List.list_position).all()
    all_cards = Card.query.filter_by(creator_id=current_user.id).order_by(Card.parent_list_id, Card.card_position).all()
    one_card = Card.query.get(card_id)
    one_list = List.query.get(one_card.parent_list_id)
    one_board = Board.query.get(id_)
    all_boards = Board.query.filter_by(is_template=False, parent_workspace_id=int(one_board.parent_workspace_id))
    all_attachments = Attachment.query.filter_by(creator_id=current_user.id).order_by(
        Attachment.attachment_upload_date).all()
    all_items_in_card = ChecklistItem.query.filter_by(creator_id=current_user.id, parent_card_id=card_id)
    completed_tasks = ChecklistItem.query.filter_by(creator_id=current_user.id, item_status=True,
                                                    parent_card_id=card_id).count()

    if all_items_in_card.count() == 0 or completed_tasks is None:
        completed_task_perc = 0
    else:
        completed_task_perc = round((completed_tasks / all_items_in_card.count()) * 100)

    if request.method == 'POST':

        if 'card_name_edit' in request.form:
            one_card.card_name = request.form['Card_Name']
            db.session.commit()
            return redirect(url_for('card', id_=one_board.board_id, card_id=card_id))

        if 'card_due_date' in request.form:
            one_card.card_dueDate = datetime.strptime(request.form['Card_Due_Date'], '%Y-%m-%d')
            db.session.commit()
            return redirect(url_for('card', id_=one_board.board_id, card_id=one_card.card_id))

        if 'remove_card_due_date' in request.form:
            # delete the entry
            one_card.card_dueDate = None
            db.session.commit()
            return redirect(url_for('card', id_=one_board.board_id, card_id=one_card.card_id))

        if 'ckeditor' in request.form:
            if request.form['ckeditor'] == '':
                one_card.card_description = None
            else:
                one_card.card_description = request.form['ckeditor']
            db.session.commit()

        if 'card_cover' in request.form:

            file = request.files['Card_Cover_Attachment']

            old_attachment = Attachment.query.filter_by(creator_id=current_user.id, is_cover_image=True,
                                                        parent_card_id=card_id).first()

            if file:
                extension = os.path.splitext(file.filename)[1].lower()
                if extension not in app.config['ALLOWED_EXTENSIONS_COVER_IMG']:
                    return '<h2>upload file with .jpg/.jpeg/.png/.gif extension only.</h2>'

                file.save(os.path.join(app.config['CARD_COVER_IMAGE'], secure_filename(file.filename)))

                new_attachment = Attachment()
                new_attachment.attachment_name = file.filename
                new_attachment.attachment_extension = extension
                new_attachment.attachment_upload_date = datetime.now()
                new_attachment.attachment_path = str(
                    f"/{app.config['CARD_COVER_IMAGE'] + secure_filename(file.filename)}")
                new_attachment.parent_card_id = card_id
                new_attachment.is_cover_image = True
                new_attachment.creator_id = current_user.id
                db.session.add(new_attachment)
                db.session.commit()

                one_card.card_cover = str(f"/{app.config['CARD_COVER_IMAGE'] + secure_filename(file.filename)}")
                db.session.commit()

            else:
                one_card.card_cover = request.form['cardCoverOption']
                db.session.commit()

            if old_attachment:
                os.remove(os.path.join(app.config['CARD_COVER_IMAGE'], old_attachment.attachment_name))
                db.session.delete(old_attachment)
                db.session.commit()

            return redirect(url_for('card', id_=one_board.board_id, card_id=one_card.card_id))

        if 'card_attachment' in request.form:
            file = request.files['Card_Attachment_File']
            extension = os.path.splitext(file.filename)[1].lower()

            if extension not in app.config['ALLOWED_EXTENSIONS_CARD_ATTACHMENT']:
                return '<h2>The file is not supported in attachment.</h2>'

            file.save(os.path.join(app.config['CARD_ATTACHMENTS'], secure_filename(file.filename)))

            new_attachment = Attachment()
            new_attachment.attachment_name = file.filename
            new_attachment.attachment_extension = extension
            new_attachment.attachment_upload_date = datetime.now()
            new_attachment.attachment_path = str(f"/{app.config['CARD_ATTACHMENTS'] + secure_filename(file.filename)}")
            new_attachment.parent_card_id = card_id
            new_attachment.is_cover_image = False
            new_attachment.creator_id = current_user.id
            db.session.add(new_attachment)
            db.session.commit()

            return redirect(url_for('card', id_=one_board.board_id, card_id=one_card.card_id))

        if 'card_checklist' in request.form:
            one_card.card_checklist_name = request.form['Card_Checklist_Name']
            db.session.commit()

        if 'edit_checklist_name' in request.form:
            one_card.card_checklist_name = request.form['Card_Checklist_Name']
            db.session.commit()

        if 'add_checklist_item' in request.form:
            new_item = ChecklistItem()
            new_item.item_name = request.form['Item_Name']
            new_item.item_status = False
            new_item.parent_card_id = card_id
            new_item.creator_id = current_user.id
            db.session.add(new_item)
            db.session.commit()

        if 'edit_item_name' in request.form:
            item_to_edit = ChecklistItem.query.filter_by(item_id=int(request.form['Item_Id'])).first()
            item_to_edit.item_name = request.form['Item_Name']
            db.session.commit()

        if 'delete_card_attachment' in request.form:
            attachment = Attachment.query.filter_by(attachment_id=request.form['attachment_id'],
                                                    parent_card_id=one_card.card_id).first()

            os.remove(os.path.join(app.config['CARD_ATTACHMENTS'], attachment.attachment_name))
            db.session.delete(attachment)
            db.session.commit()

            return redirect(url_for('card', id_=one_board.board_id, card_id=one_card.card_id))

        if 'move_card_form' in request.form:
            all_cards_in_dest_list = Card.query.filter_by(
                parent_list_id=int(request.form['Dest_List_Move_Card'][1:]))
            all_cards_in_current_list = Card.query.filter_by(
                parent_list_id=int(request.form['Current_List_Id']))

            # move card in same board
            if int(request.form['Dest_Board_Move_Card']) == one_board.board_id:

                if (request.form['Current_Card_Position'] != request.form['Dest_Position_Move_Card'] and
                        int(request.form['Dest_List_Move_Card'][1:]) == one_list.list_id):

                    x = 10000

                    current_card = Card.query.filter_by(card_position=request.form['Current_Card_Position'],
                                                        parent_list_id=request.form['Dest_List_Move_Card'][1:]).first()

                    current_card.card_position = x
                    db.session.commit()

                    if request.form['Current_Card_Position'] < request.form['Dest_Position_Move_Card']:

                        move_cards_up(int(request.form['Current_Card_Position']) + 1,
                                      int(request.form['Dest_Position_Move_Card']) + 1,
                                      int(request.form['Current_List_Id']))

                    elif request.form['Current_Card_Position'] > request.form['Dest_Position_Move_Card']:
                        # decrease position

                        move_cards_down(-(int(request.form['Current_Card_Position']) - 1),
                                        -(int(request.form['Dest_Position_Move_Card']) - 1),
                                        int(request.form['Current_List_Id']))

                    destination_card = Card.query.filter_by(card_position=x, parent_list_id=one_list.list_id).first()
                    destination_card.card_position = int(request.form['Dest_Position_Move_Card'])
                    db.session.commit()

                elif int(request.form['Dest_List_Move_Card'][1:]) != one_list.list_id:

                    if request.form['Dest_Position_Move_Card'] == 'newPosition':

                        current_card = Card.query.filter_by(card_position=request.form['Current_Card_Position'],
                                                            parent_list_id=one_list.list_id).first()

                        current_card.card_position = all_cards_in_dest_list.count() + 1
                        current_card.parent_list_id = int(request.form['Dest_List_Move_Card'][1:])
                        db.session.commit()

                        move_cards_up(int(request.form['Current_Card_Position']) + 1,
                                      int(all_cards_in_current_list.count() + 2),
                                      one_list.list_id)

                    elif request.form['Dest_Position_Move_Card'] != 'newPosition':

                        x = 10000

                        current_card = Card.query.filter_by(card_position=request.form['Current_Card_Position'],
                                                            parent_list_id=one_list.list_id).first()

                        current_card.card_position = x
                        current_card.parent_list_id = int(request.form['Dest_List_Move_Card'][1:])
                        db.session.commit()

                        move_cards_up(int(request.form['Current_Card_Position']) + 1,
                                      int(all_cards_in_current_list.count() + 2),
                                      one_list.list_id)

                        move_cards_down(-(int(all_cards_in_dest_list.count()) - 1),
                                        -(int(request.form['Dest_Position_Move_Card']) - 1),
                                        int(request.form['Dest_List_Move_Card'][1:]))

                        destination_card = Card.query.filter_by(
                            card_position=x,
                            parent_list_id=request.form['Dest_List_Move_Card'][1:]).first()
                        destination_card.card_position = int(request.form['Dest_Position_Move_Card'])
                        db.session.commit()

            elif int(request.form['Dest_Board_Move_Card']) != one_board.board_id:

                if request.form['Dest_Position_Move_Card'] == 'newPosition':

                    current_card = Card.query.filter_by(card_position=request.form['Current_Card_Position'],
                                                        parent_list_id=one_list.list_id).first()

                    current_card.card_position = all_cards_in_dest_list.count() + 1
                    current_card.parent_list_id = int(request.form['Dest_List_Move_Card'][1:])
                    db.session.commit()

                    move_cards_up(int(request.form['Current_Card_Position']) + 1,
                                  int(all_cards_in_current_list.count() + 2), one_list.list_id)

                elif request.form['Dest_Position_Move_Card'] != 'newPosition':

                    x = 10000

                    current_card = Card.query.filter_by(card_position=request.form['Current_Card_Position'],
                                                        parent_list_id=one_list.list_id).first()

                    current_card.card_position = x
                    current_card.parent_list_id = int(request.form['Dest_List_Move_Card'][1:])
                    db.session.commit()

                    move_cards_up(int(request.form['Current_Card_Position']) + 1,
                                  int(all_cards_in_current_list.count() + 2), one_list.list_id)

                    move_cards_down(-(int(all_cards_in_dest_list.count()) - 1),
                                    -(int(request.form['Dest_Position_Move_Card']) - 1),
                                    int(request.form['Dest_List_Move_Card'][1:]))

                    destination_card = Card.query.filter_by(
                        card_position=x,
                        parent_list_id=request.form['Dest_List_Move_Card'][1:]).first()

                    destination_card.card_position = int(request.form['Dest_Position_Move_Card'])
                    db.session.commit()
                return redirect(url_for('board', board_id=one_board.board_id))

        if 'copy_card_form' in request.form:

            all_cards_in_dest_list = Card.query.filter_by(
                parent_list_id=int(request.form['Dest_List_Copy_Card'][1:]))
            all_cards_in_current_list = Card.query.filter_by(
                parent_list_id=int(request.form['Current_List_Id']))

            if (request.form['Current_Card_Position'] != request.form['Dest_Position_Copy_Card'] and
                    int(request.form['Dest_List_Copy_Card'][1:]) == one_list.list_id):

                move_cards_down(-int(all_cards_in_current_list.count()),
                                -(int(request.form['Dest_Position_Copy_Card']) - 1),
                                int(request.form['Current_List_Id']))

                clone_card(card_id=card_id, updated_name=request.form['Card_Name'],
                           updated_parent_id=request.form['Current_List_Id'],
                           updated_position=request.form['Dest_Position_Copy_Card'])

            elif int(request.form['Dest_List_Copy_Card'][1:]) != one_list.list_id:

                if request.form['Dest_Position_Copy_Card'] == 'newPosition':

                    clone_card(card_id=card_id, updated_name=request.form['Card_Name'],
                               updated_parent_id=int(request.form['Dest_List_Copy_Card'][1:]),
                               updated_position=all_cards_in_dest_list.count() + 1)

                elif request.form['Dest_Position_Copy_Card'] != 'newPosition':

                    move_cards_down(-int(all_cards_in_dest_list.count()),
                                    -(int(request.form['Dest_Position_Copy_Card']) - 1),
                                    int(request.form['Dest_List_Copy_Card'][1:]))

                    clone_card(card_id=card_id, updated_name=request.form['Card_Name'],
                               updated_parent_id=int(request.form['Dest_List_Copy_Card'][1:]),
                               updated_position=int(request.form['Dest_Position_Copy_Card']))

            if int(request.form['Dest_Board_Copy_Card']) != one_board.board_id:

                if request.form['Dest_Position_Copy_Card'] == 'newPosition':

                    clone_card(card_id=card_id, updated_name=request.form['Card_Name'],
                               updated_parent_id=request.form['Dest_List_Copy_Card'][1:],
                               updated_position=all_cards_in_dest_list.count() + 1)

                elif request.form['Dest_Position_Copy_Card'] != 'newPosition':

                    move_cards_down(-int(all_cards_in_dest_list.count()),
                                    -(int(request.form['Dest_Position_Copy_Card']) - 1),
                                    int(request.form['Dest_List_Copy_Card'][1:]))

                    clone_card(card_id=card_id, updated_name=request.form['Card_Name'],
                               updated_parent_id=request.form['Dest_List_Copy_Card'][1:],
                               updated_position=request.form['Dest_Position_Copy_Card'])

                return redirect(url_for('board', board_id=one_board.board_id))

        if 'checklist_item_checkbox' in request.form:
            item_to_edit = ChecklistItem.query.filter_by(item_id=int(request.form['Item_Id'])).first()
            item_to_edit.item_status = not item_to_edit.item_status
            db.session.commit()

        if 'delete_checklist' in request.form:

            for item in all_items_in_card:
                db.session.delete(item)
            db.session.commit()

            one_card.card_checklist_name = None
            db.session.commit()

        if 'delete_checklist_item' in request.form:
            item_to_delete = ChecklistItem.query.filter_by(parent_card_id=card_id,
                                                           item_id=request.form['Item_Id']).first()
            db.session.delete(item_to_delete)
            db.session.commit()

        if 'delete_card' in request.form:

            items_to_delete = ChecklistItem.query.filter_by(parent_card_id=card_id)
            attachments_to_delete = Attachment.query.filter_by(is_cover_image=False, parent_card_id=card_id)
            cover_image_attachment = Attachment.query.filter_by(is_cover_image=True, parent_card_id=card_id).first()

            if attachments_to_delete:
                for attachment in attachments_to_delete:
                    os.remove(os.path.join(app.config['CARD_ATTACHMENTS'], attachment.attachment_name))
                    db.session.delete(attachment)

                db.session.commit()

            if cover_image_attachment:
                os.remove(os.path.join(app.config['CARD_COVER_IMAGE'], cover_image_attachment.attachment_name))

            if items_to_delete:
                for i in items_to_delete:
                    db.session.delete(i)
                db.session.commit()

            db.session.delete(one_card)
            db.session.commit()

            return redirect(url_for('board', board_id=one_board.board_id))

        return redirect(url_for('card', id_=one_board.board_id, card_id=one_card.card_id))

    return render_template('card.html', one_board=one_board, one_list=one_list, one_card=one_card,
                           all_boards=all_boards, all_lists=all_lists, all_cards=all_cards, all_colors=all_colors,
                           all_images=all_images, all_attachments=all_attachments, all_items=all_items,
                           completed_task_perc=completed_task_perc)


@app.errorhandler(413)
def request_entity_too_large(error):
    return f'<h2 style="color: red;">File is bigger than 8Mb upload limit.<h2>\n{error}'


if __name__ == '__main__':
    app.run(debug=True)

# secure_filename changes file name like replace spaces with _ .
# file.save(f"all_uploads/{secure_filename(file.filename)}")
# joining upload path and upload filename
