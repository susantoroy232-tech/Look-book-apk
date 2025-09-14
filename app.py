from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os


app=Flask(__name__,template_folder="template")
app.secret_key = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///social.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    profile_picture = db.Column(db.String(200), default='default.jpg')
    bio = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')
    shares = db.relationship('Share', backref='post', lazy=True, cascade='all, delete-orphan')

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Share(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    platform = db.Column(db.String(20))  # 'facebook', 'twitter', 'direct', etc.

# Create database tables
with app.app_context():
    db.create_all()

# API Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
        
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400
        
    user = User(username=username, email=email, password=password)
    db.session.add(user)
    db.session.commit()
    
    session['user_id'] = user.id
    return jsonify({'message': 'User created successfully', 'user': {
        'id': user.id,
        'username': user.username,
        'email': user.email
    }}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = User.query.filter_by(username=username, password=password).first()
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
        
    session['user_id'] = user.id
    return jsonify({'message': 'Login successful', 'user': {
        'id': user.id,
        'username': user.username,
        'email': user.email
    }})

@app.route('/api/posts', methods=['GET'])
def get_posts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '')
    
    query = Post.query.order_by(Post.created_at.desc())
    
    if search:
        query = query.filter(Post.content.ilike(f'%{search}%'))
    
    posts = query.paginate(page=page, per_page=per_page, error_out=False)
    
    posts_data = []
    for post in posts.items:
        posts_data.append({
            'id': post.id,
            'content': post.content,
            'image': post.image,
            'created_at': post.created_at.isoformat(),
            'user': {
                'id': post.author.id,
                'username': post.author.username,
                'profile_picture': post.author.profile_picture
            },
            'likes_count': len(post.likes),
            'comments_count': len(post.comments),
            'shares_count': len(post.shares),
            'is_liked': any(like.user_id == session.get('user_id') for like in post.likes),
            'is_shared': any(share.user_id == session.get('user_id') for share in post.shares)
        })
    
    return jsonify({
        'posts': posts_data,
        'total': posts.total,
        'pages': posts.pages,
        'current_page': page
    })

@app.route('/api/posts', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    content = data.get('content')
    image = data.get('image')
    
    if not content:
        return jsonify({'error': 'Content is required'}), 400
        
    post = Post(content=content, image=image, user_id=session['user_id'])
    db.session.add(post)
    db.session.commit()
    
    return jsonify({
        'message': 'Post created successfully',
        'post': {
            'id': post.id,
            'content': post.content,
            'image': post.image,
            'created_at': post.created_at.isoformat()
        }
    }), 201

@app.route('/api/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403
        
    data = request.json
    content = data.get('content')
    
    if not content:
        return jsonify({'error': 'Content is required'}), 400
        
    post.content = content
    db.session.commit()
    
    return jsonify({'message': 'Post updated successfully'})

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403
        
    db.session.delete(post)
    db.session.commit()
    
    return jsonify({'message': 'Post deleted successfully'})

@app.route('/api/posts/<int:post_id>/like', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    post = Post.query.get_or_404(post_id)
    user_id = session['user_id']
    
    # Check if user already liked this post
    existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({'message': 'Post unliked', 'liked': False})
    
    like = Like(user_id=user_id, post_id=post_id)
    db.session.add(like)
    db.session.commit()
    
    return jsonify({'message': 'Post liked', 'liked': True})

@app.route('/api/posts/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    content = data.get('content')
    
    if not content:
        return jsonify({'error': 'Content is required'}), 400
        
    comment = Comment(content=content, user_id=session['user_id'], post_id=post_id)
    db.session.add(comment)
    db.session.commit()
    
    return jsonify({
        'message': 'Comment added successfully',
        'comment': {
            'id': comment.id,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
            'user': {
                'id': comment.author.id,
                'username': comment.author.username,
                'profile_picture': comment.author.profile_picture
            }
        }
    }), 201

@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    comment = Comment.query.get_or_404(comment_id)
    
    if comment.user_id != session['user_id']:
        return jsonify({'error': 'Forbidden'}), 403
        
    db.session.delete(comment)
    db.session.commit()
    
    return jsonify({'message': 'Comment deleted successfully'})

@app.route('/api/posts/<int:post_id>/share', methods=['POST'])
def share_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    platform = data.get('platform', 'direct')
    
    share = Share(user_id=session['user_id'], post_id=post_id, platform=platform)
    db.session.add(share)
    db.session.commit()
    
    return jsonify({'message': f'Post shared on {platform}'})

@app.route('/api/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'profile_picture': user.profile_picture,
        'bio': user.bio,
        'created_at': user.created_at.isoformat()
    })

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if 'user_id' not in session or session['user_id'] != user_id:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user = User.query.get_or_404(user_id)
    data = request.json
    
    if 'username' in data:
        user.username = data['username']
    if 'bio' in data:
        user.bio = data['bio']
    
    db.session.commit()
    
    return jsonify({'message': 'Profile updated successfully'})

if __name__ == '__main__':
    app.run(debug=True)