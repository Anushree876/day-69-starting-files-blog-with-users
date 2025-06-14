import os
from datetime import date
from typing import List
import werkzeug.security
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm,LoginForm,CommentForm
import smtplib
from dotenv import load_dotenv
'''
Make sure the required packages are installed: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from the requirements.txt for this project.
'''
load_dotenv()
MY_EMAIL=os.getenv("MY_EMAIL")
MY_PASSWORD=os.getenv("MY_PASSWORD")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_KEY")
ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager=LoginManager()
login_manager.init_app(app)

gravatar=Gravatar(app,
                  size=100,
                  rating="g",
                  default="retro",
                  force_default=False,
                  force_lower=False,
                  use_ssl=False,
                  base_url=None)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,int(user_id))


# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI")
db = SQLAlchemy(model_class=Base)
db.init_app(app)


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author=relationship("User",back_populates="posts")
    author_id:Mapped[int]=mapped_column(Integer,db.ForeignKey("user.id"))
    comments=relationship("Comment",back_populates="parent_post")

class User(db.Model,UserMixin):
    __tablename__="user"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    email:Mapped[str]=mapped_column(String,unique=True,nullable=False)
    password:Mapped[str]=mapped_column(String,nullable=False)
    name:Mapped[str]=mapped_column(String,nullable=False)
    posts=relationship("BlogPost",back_populates="author")
    comments=relationship("Comment",back_populates="comment_author")

class Comment(db.Model):
    __tablename__="comments"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    text:Mapped[str]=mapped_column(String,nullable=False)
    author_id:Mapped[int]=mapped_column(Integer,db.ForeignKey("user.id"))
    comment_author=relationship("User",back_populates="comments")
    post_id:Mapped[int]=mapped_column(Integer,db.ForeignKey("blog_posts.id"))
    parent_post=relationship("BlogPost",back_populates="comments")

def admin_only(f):
    @wraps(f)
    def wrapper(*args,**kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args,**kwargs)
    return wrapper



# TODO: Create a User table for all your registered users. 


with app.app_context():
    db.create_all()


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register',methods=["GET","POST"])
def register():
    register_form=RegisterForm()

    if register_form.validate_on_submit():
        hash_and_salted_password =generate_password_hash(
            register_form.password.data,
            method='pbkdf2:sha256',
            salt_length=8)
        email = register_form.email.data
        password = hash_and_salted_password
        name = register_form.name.data
        user=User(
            email=email,
            password=password,
            name=name
        )
        already_their=db.session.execute(db.select(User).where(User.email==email)).scalar()
        if already_their:
            flash("You've already signed up with that email, log in instead.")
            return redirect(url_for("login"))
        else:
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("get_all_posts"))
    return render_template("register.html",form=register_form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login',methods=["GET","POST"])
def login():
    login_form=LoginForm()
    if login_form.validate_on_submit():
        email=login_form.email.data
        password=login_form.password.data
        user=db.session.execute(db.select(User).where(User.email==email)).scalar()
        if not user:
            flash("That email doesn't exist, please try again.")
        elif not check_password_hash(user.password,password):
            flash("Incorrect password, please try again.")

        elif user and check_password_hash(user.password,password):
            login_user(user)
            return redirect(url_for("get_all_posts"))

    return render_template("login.html",form=login_form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts)


# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>",methods=["GET","POST"])
def show_post(post_id):
    comment_form=CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    if comment_form.validate_on_submit():
        comment=Comment(
            text=comment_form.text.data,
            comment_author=current_user,
            parent_post=requested_post

        )
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for("show_post",post_id=post_id))
    return render_template("post.html", post=requested_post,form=comment_form)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact",methods=["GET","POST"])
def contact():
    if request.method=="POST":
        name=request.form.get("name")
        email=request.form.get("email")
        message=request.form.get("message")
        phone=request.form.get("phone")

        with smtplib.SMTP("smtp.gmail.com",587) as connection:
            connection.starttls()
            connection.login(user=MY_EMAIL,password=MY_PASSWORD)
            connection.sendmail(
                from_addr=MY_EMAIL,
                to_addrs=MY_EMAIL,
                msg=f"{name}\n{email}\n{phone}\n{message}"
            )
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False)
