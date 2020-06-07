import json
import re
import yaml
from flask import Flask, request, abort
from gitlab import Gitlab
from pandas import DataFrame

app = Flask(__name__)
gl = Gitlab.from_config('global', ['gitlab.cfg'])
secretkey = "hogehoge"

DESC_PATTERN = re.compile(r'```yaml\n*((.|\s)*)\n*```')
NOTE_PATTERN = re.compile(r'```yaml\n*((.|\s)*)\n*```')


@app.route("/", methods=["POST"])
def index():
    if (request.headers.get("X-Gitlab-Token", "") != secretkey) or (request.headers.get("X-Gitlab-Event", "") != "Note Hook"):
        abort(400)

    data = json.loads(request.get_data())
    if ('merge_request' in data):
        project_id = data["project"]["id"]
        mr_id = data["merge_request"]["iid"]

        try:
            mr = gl.projects.get(
                project_id, lazy=True).mergerequests.get(mr_id)
            review_list = get_review_list(mr)
            if review_list:
                aggregate = aggregate_review(review_list)
                update_mr_description(mr, aggregate)
            return "ok"
        except:
            abort(500)
    else:
        return "ok"


def get_review_list(mr):
    """
    対象のMRのdisucussionからレビュー記録を抽出
    """
    review_list = []
    for d in mr.discussions.list(all=True):
        notes = d.attributes["notes"]
        for n in notes:
            note_body = n['body']
            match = NOTE_PATTERN.search(note_body)
            if match:
                review = yaml.safe_load(match.group(1))
                if type(review) == dict:
                    review_list.append(review)
    return review_list


def aggregate_review(review_list):
    """
    レビュー記録を集計
    """
    aggregate = {}
    df = DataFrame(review_list)
    for col, item in df.iteritems():
        aggregate[col] = df.groupby(col).size().to_dict()
    return aggregate


def update_mr_description(mr, aggregate):
    """
    レビュー記録の集計情報をMRのdescriptionに記載する
    """
    insert_str = f'```yaml\n{yaml.dump(aggregate, allow_unicode=True)}```'
    match = DESC_PATTERN.search(mr.description)
    if match:
        # 既に記載がある場合
        # 集計値に変更がある場合だけ更新
        current = yaml.safe_load(match.group(1))
        if not current == aggregate:
            mr.description = DESC_PATTERN.sub(insert_str, mr.description)
    else:
        # 記載がない場合は追記
        mr.description = f'{mr.description}\n\n{insert_str}'
    mr.save()


if __name__ == "__main__":
    # TODO: envを拾ってdebug=Falseにする
    app.run(debug=True, host="0.0.0.0", port=5000)
