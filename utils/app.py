import requests

import pickle

import doMovie
import doMovieNew
from doMovies import similar_films
from flask import Flask, render_template, redirect, url_for, request, session, escape, json, jsonify, flash
from dbo import *
from datetime import timedelta

from reporter import get_stats_data

app = Flask(__name__)
app.config['DEBUG'] = True  # 开启 debug 模式
app.config['SECRET_KEY'] = 'hONyY9FjRvQH'  # 加密令牌
# 自动重载模板文件
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

with open("./static/model/pca.pkl", "rb") as f:
    model_pca = pickle.load(f)


# 设置静态文件缓存过期时间
# app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(seconds=1)


def user_is_logged():  # 校验 session 中存储的用户信息是否有效
    msg = {'result': False, 'info': 'session wrong'}
    if 'username' in session and 'password' in session:
        username = escape(session['username'])
        password = escape(session['password'])
        msg = user_login(username, password)  # 校验 Cookie 存储的信息是否正确
        return msg
    else:
        session.clear()
        return msg


@app.route('/')
def index():
    msg = user_is_logged()
    same_like_movie = None
    sub = '00Mvye3K2NYPiezd'
    movie = doMovie.getFilmDict(sub)
    if msg['result']:
        username = escape(session['username'])
        same_like_movie = doMovieNew.SamerLikerPro(username, sub, model_pca)
    suggest = doMovieNew.recommendMoviesPro(sub)
    if same_like_movie:
        same_like_movie = same_like_movie[:5]
    if suggest:
        suggest = suggest[:5]
    comments = get_latest_comment()['comments']
    if type(suggest) == tuple:
        suggestMovie = suggest[0]
        vistedUsers = suggest[1]
        return render_template(
            'index.html',
            movie=movie,
            suggestMovie=suggestMovie,
            vistedUsers=vistedUsers,
            same_like_movie=same_like_movie,
            comments=comments,
            message=request.args.get('message'))
    suggestMovie = suggest
    return render_template(
        'index.html',
        movie=movie,
        suggestMovie=suggestMovie,
        same_like_movie=same_like_movie,
        comments=comments,
        message=request.args.get('message'))


@app.route('/data_report')
def data_report():
    # 获取数据报表的统计数据
    stats_data = get_stats_data()
    return render_template('data_report.html', stats_data=stats_data)


@app.route('/movies_list')
def movies_list():
    """
    跳转电影分类页面
    :return:
    """
    return render_template('moviegridfw.html')


@app.route('/movie/<string:sub>/', methods=['GET', 'POST'])
def change_recommend(sub):
    """
    换一批推荐的电影
    :param sub: 当前电影的id
    :return: 推荐的电影列表
    """
    same_like_movie = []
    msg = user_is_logged()
    if msg['result']:
        username = escape(session['username'])
        same_like_movie = doMovieNew.SamerLikerPro(username, sub, model_pca)
        return jsonify(same_like_movie)
    else:
        suggest = doMovieNew.recommendMoviesPro(sub)
        return jsonify(suggest)


@app.route('/subject/<string:sub>/')
def subject(sub):
    msg = user_is_logged()
    same_like_movie = None
    movie = doMovie.getFilmDict(sub)

    if movie is None:
        return render_template('404.html')
    if msg['result']:
        username = escape(session['username'])
        same_like_movie = doMovieNew.SamerLikerPro(username, sub, model_pca)
    suggest = doMovieNew.recommendMoviesPro(sub)
    comments = get_comment(sub)['comments']
    if type(suggest) == tuple:
        suggestMovie = suggest[0]
        vistedUsers = suggest[1]
        return render_template(
            'moviesingle.html',
            movie=movie,
            suggestMovie=suggestMovie,
            vistedUsers=vistedUsers,
            same_like_movie=same_like_movie,
            comments=comments,
            message=request.args.get('message'))
    suggestMovie = suggest
    return render_template(
        'moviesingle.html',
        movie=movie,
        suggestMovie=suggestMovie,
        same_like_movie=same_like_movie,
        comments=comments,
        message=request.args.get('message'))


@app.route('/addVited/<string:sub>')
def addVited(sub):
    msg = user_is_logged()
    if msg['result']:
        username = escape(session['username'])
        doMovie.addVited(sub, username)
    return redirect(url_for('subject', sub=sub))


@app.route('/show_uname', methods=['GET', 'POST'])
def show_uname():
    if request.method == 'GET':
        return render_template('404.html')
    else:
        msg = user_is_logged()
        if msg['result']:
            msg['info'] = escape(session['username'])
        else:
            msg['info'] = '提示：用户名不存在！'
        return json.dumps(msg)


@app.route('/show_films', methods=['GET', 'POST'])
def show_films():
    if request.method == 'GET':
        return render_template('404.html')
    else:
        like = request.values.get('like')
        sort = request.values.get('sort')
        page = request.values.get('page')
        films = get_films(like, sort, int(page))
        return json.dumps(films)


@app.route('/show_films_year', methods=['GET', 'POST'])
def show_films_year():
    if request.method == 'GET':
        return render_template('404.html')
    else:
        year = request.values.get('year')
        sort = request.values.get('sort')
        page = request.values.get('page')
        films = get_films_year(year, sort, int(page))
        # print(films)
        return json.dumps(films)


@app.route('/search_film', methods=['GET', 'POST'])
def search_film():
    film_name = request.values.get('search_text')
    # print("film_name", film_name)
    film = find_film(film_name)
    return json.dumps(film)


@app.route('/show_collection', methods=['GET', 'POST'])
def show_collection():
    """
    电影详情页显示收藏
    :return:
    """
    if request.method == 'GET':
        return render_template('404.html')
    else:
        msg = user_is_logged()
        if msg['result']:
            # 调用函数获取喜欢的列表
            username = str(escape(session['username']))
            # print(username)
            collection_str = ",".join(get_collection(username))
            collection_list = collection_str.split("-")

            return json.dumps(collection_list)
        else:
            return json.dumps([""])


@app.route('/show_likes', methods=['GET', 'POST'])
def show_likes():
    """
    电影详情页显示喜欢/已喜欢
    :return:
    """
    if request.method == 'GET':
        return render_template('404.html')
    else:
        msg = user_is_logged()
        if msg['result']:
            # 调用函数获取喜欢的列表
            username = str(escape(session['username']))
            # print(username)
            likes_str = ",".join(get_likes(username))
            likes_list = likes_str.split("-")

            return json.dumps(likes_list)
        else:
            return json.dumps([""])


@app.route('/changeCollection/<string:sub>', methods=['GET', 'POST'])
def changeCollection(sub):
    """
    切换电影的喜欢状态
    :param sub:
    :return:
    """
    msg = user_is_logged()
    if msg['result']:
        # 调用函数获取喜欢的列表
        username = str(escape(session['username']))
        # print(username)
        collection_str = ",".join(get_collection(username))
        collection_list = collection_str.split("-")
        # 根据当前sub是否再likes_list中来切换喜欢状态
        message = ''
        if sub in collection_list:
            collection_list.remove(sub)
            likes_str = '-'.join(collection_list)
            message = "提示:" + "取消收藏"
        else:
            collection_list.append(sub)
            likes_str = '-'.join(collection_list)
            message = "提示:" + "已收藏"
        # 更新likes字段
        msg = update_collection(likes_str, username)
        if msg['result']:
            return redirect(url_for('subject', sub=sub, message=message))
        else:
            message = "提示：" + msg['info'] + "，请重新操作！"
            return redirect(url_for('subject', sub=sub, message=message))
    else:
        return redirect(url_for('subject', sub=sub, message="提示：未登录"))


@app.route('/remove_collection_fav/<string:sub>')
def remove_collection_fav(sub):
    msg = user_is_logged()
    if msg['result']:
        # 调用函数获取喜欢的列表
        username = str(escape(session['username']))
        # print(username)
        collection_str = ",".join(get_collection(username))
        collection_list = collection_str.split("-")
        # 根据当前sub是否再likes_list中来切换喜欢状态
        if sub in collection_list:
            collection_list.remove(sub)
            likes_str = '-'.join(collection_list)
            message = "提示:" + "取消收藏"
            # 更新likes字段
            msg = update_collection(likes_str, username)
        else:
            likes_str = '-'.join(collection_list)
            message = "提示:" + "已收藏"
            msg = {'result': False}
        if msg['result']:
            return redirect(url_for('show_favorite', message=message))
        else:
            if 'info' in msg.keys():
                message = "提示：" + msg['info'] + "，请重新操作！"
            else:
                message = "提示：未找到指定电影！"
            return redirect(url_for('show_favorite', message=message))
    else:
        return redirect(url_for('index', message="提示：未登录"))


@app.route('/remove_comment_com_page/<int:com_id>')
def remove_comment_com_page(com_id):
    remove_comment(com_id)
    return redirect(url_for('show_comment'))


@app.route('/changeLikes/<string:sub>', methods=['GET', 'POST'])
def changeLikes(sub):
    """
    切换电影的喜欢状态
    :param sub:
    :return:
    """
    msg = user_is_logged()
    if msg['result']:
        # 调用函数获取喜欢的列表
        username = str(escape(session['username']))
        # print(username)
        likes_str = ",".join(get_likes(username))
        likes_list = likes_str.split("-")
        # 根据当前sub是否再likes_list中来切换喜欢状态
        message = ''
        if sub in likes_list:
            likes_list.remove(sub)
            likes_str = '-'.join(likes_list)
            message = "提示:" + "取消喜欢"
        else:
            likes_list.append(sub)
            likes_str = '-'.join(likes_list)
            message = "提示:" + "已喜欢"
        # 更新likes字段
        msg = update_likes(likes_str, username)
        if msg['result']:
            return redirect(url_for('subject', sub=sub, message=message))
        else:
            message = "提示：" + msg['info'] + "，请重新操作！"
            return redirect(url_for('subject', sub=sub, message=message))
    else:
        return redirect(url_for('subject', sub=sub, message="提示：未登录"))


"""
提交评论及评分
"""


@app.route('/updata_evaluation', methods=['GET', 'POST'])
def updata_evaluation():
    msg = user_is_logged()
    subject = request.form.get('subject')
    if msg['result']:
        # 调用函数获取喜欢的列表
        username = str(escape(session['username']))
        # print(username)
        # 获取电影id 评论及评分
        comment = request.form.get('comment')
        customerEvaluationComment = request.form.get('customerEvaluationLevel')
        title = request.form.get('title')
        # print(username, comment, customerEvaluationComment, subject)
        message = ''
        # 插入评论
        msg = insert_evaluation(username, comment, float(customerEvaluationComment) * 2, subject, title)
        if msg['result']:
            return jsonify({'message': '评论成功'}), 200
        else:
            message = "提示：" + msg['info'] + "，请重新操作！"
            return jsonify({'error': message}), 500
    else:
        return jsonify({'error': msg['info']}), 500


@app.route('/show_recomm', methods=['GET', 'POST'])
def show_recomm():
    if request.method == 'GET':
        return render_template('404.html')
    else:
        like = request.values.get('like')
        sort = request.values.get('sort')
        page = request.values.get('page')
        films = similar_films(like, sort, int(page))
        return json.dumps(films)


@app.route('/user_info', methods=['GET', 'POST'])
def show_userInfo():
    msg = user_is_logged()
    genres = ['剧情', '喜剧', '动作', '爱情', '科幻', '动画', '悬疑', '惊悚', '恐怖', '纪录片', '短片', '情色', '同性',
              '音乐', '歌舞', '家庭', '儿童', '传记', '历史', '战争', '犯罪', '西部', '奇幻', '冒险', '灾难', '武侠',
              '古装', '运动', '黑色电影']
    if msg['result']:
        username = escape(session['username'])
        # print("username" + username)
        user = get_user(username=username)
        return render_template('userprofile.html', user=user, genres=genres)
    else:
        msg['info'] = '提示：用户名不存在！'
    return json.dumps(msg)


@app.route('/user_info_modify', methods=['POST', 'GET'])
def user_info_modify():
    msg = user_is_logged()

    if msg['result']:
        love = '-'.join(request.form.getlist('love[]'))
        # 修改数据
        username = str(escape(session['username']))
        msg = user_modify(username, {'love': love})
        user = get_user(username=username)
        genres = ['剧情', '喜剧', '动作', '爱情', '科幻', '动画', '悬疑', '惊悚', '恐怖', '纪录片', '短片', '情色', '同性',
                  '音乐', '歌舞', '家庭', '儿童', '传记', '历史', '战争', '犯罪', '西部', '奇幻', '冒险', '灾难', '武侠',
                  '古装', '运动', '黑色电影']
        if msg['result']:
            flash('偏好设置成功', 'success')
            return render_template('userprofile.html', user=user, genres=genres)
        else:
            flash('偏好设置成功', 'success')
            return render_template('userprofile.html', user=user, genres=genres)
    else:
        return render_template('index.html')


@app.route('/login', methods=['GET'])
def login():
    msg = user_is_logged()
    if msg['result']:
        return redirect(url_for('index'))
    else:
        return render_template('login.html', message=request.args.get('message'))


@app.route('/register', methods=['GET'])
def register():
    msg = user_is_logged()
    if msg['result']:
        return redirect(url_for('index'))
    else:
        return render_template('register.html')


@app.route('/forget', methods=['GET'])
def forget():
    msg = user_is_logged()
    if msg['result']:
        return redirect(url_for('index'))
    else:
        return render_template('forget.html')


@app.route('/login', methods=['POST'])
def login_form():
    username = request.values.get('username')
    password = request.values.get('password')
    msg = user_login(username, password)
    if msg['result']:
        session['username'] = username
        session['password'] = password

        return jsonify({'result': 'success', 'message': '登录成功！'})
    else:

        return jsonify({'result': 'error', 'message': '密码错误！'})


@app.route('/register', methods=['POST'])
def register_form():
    username = request.values.get('username')
    password = request.values.get('password')
    email = request.values.get('email')
    msg = user_register(username, password, email)
    if msg['result']:
        message = "提示:" + msg['info'] + ", 请登录账户！"
        return redirect(url_for('index', message=message))
    else:
        message = "提示：" + msg['info'] + "，请重新输入！"
        return redirect(url_for('index', message=message))


@app.route('/forget', methods=['POST'])
def forget_form():
    username = request.values.get('username')
    password = request.values.get('password')
    email = request.values.get('email')
    msg = user_forget(username, password, email)
    if msg['result']:
        return jsonify({'result': 'success', 'message': '密码找回成功！'})
    else:
        return jsonify({'result': 'error', 'message': '信息错误！'})


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('username', None)
    session.pop('password', None)
    # session.clear()
    return redirect(url_for('index'))


@app.errorhandler(404)  # 404页面
def page_not_found(error):
    return render_template('404.html')


@app.route('/show_favorite')
def show_favorite():
    if not user_is_logged():
        return render_template('404.html')
    username = str(escape(session['username']))
    user = get_user(username)
    fav_films = user['collection'].split('-')
    fav_info = sorted(get_multi_films(fav_films).to_dict(orient='records'), key=lambda x: fav_films.index(x['subject']),
                      reverse=True)
    for itm in fav_info:
        itm['director'] = itm['director'].split('{}')
        itm['starring'] = itm['starring'].split('{}')
    print(fav_info)
    return render_template('userfavoritelist.html',
                           user=user,
                           fav_films_len=len(fav_films),
                           fav_info=fav_info,
                           )


@app.route('/show_comment')
def show_comment():
    if not user_is_logged():
        return render_template('404.html')
    username = str(escape(session['username']))
    user = get_user(username)
    user_comment = sorted(get_user_comment(username), key=lambda x: x['subject_id'])
    films = [itm['subject_id'] for itm in user_comment]
    if films:
        films_info = get_multi_films(films).to_dict(orient='records')
    else:
        films_info = []
    films_info = sorted(films_info, key=lambda x: x['subject'])
    for uc, fm in zip(user_comment, films_info):
        uc['strb'] = fm['strb']
        uc['title'] = fm['title']
    user_comment = sorted(user_comment, key=lambda x: x['insert_time'], reverse=True)
    return render_template('userrate.html',
                           user=user,
                           comments=user_comment,
                           message=request.args.get('message')
                           )
def hello_word():
    print('test pull request')

if __name__ == '__main__':
    app.run(host='0.0.0.0')