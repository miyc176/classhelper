#!/usr/bin/env python3
"""Build one standalone classic knowledge game from the polished template."""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path

from classic_payload import build_payload, load_knowledge

LABELS={"memory":"知识翻牌","tictactoe":"答题井字棋","flappy":"飞翔判断","shooter":"雷霆战机","puzzle":"知识拼图"}

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("knowledge_json")
    parser.add_argument("--mode",required=True,choices=LABELS)
    parser.add_argument("--out",required=True)
    parser.add_argument("--title")
    parser.add_argument("--seed",type=int,default=11)
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    data=load_knowledge(Path(args.knowledge_json).resolve())
    arcade=build_payload(data,args.seed)
    mode=args.mode
    content=arcade["tictactoe"] if mode == "shooter" else arcade[mode]
    if mode == "puzzle":
        content = content[:6]
    covered_ids = [str(item["id"]) for item in content]
    payload={"title":args.title or f"{data.get('course_title','课程')}：{LABELS[mode]}","mode":mode,"coverage":list(dict.fromkeys(covered_ids))}
    payload["items"]=content
    payload["total"]=4 if mode=="puzzle" else (len(content) if mode!="tictactoe" else 9)
    out=Path(args.out).resolve()
    if out.exists():
        if not args.force: raise FileExistsError(out)
        shutil.rmtree(out)
    template=Path(__file__).resolve().parents[1]/"assets"/"standalone-classic-template"
    shutil.copytree(template,out)
    (out/"game-data.js").write_text("window.STANDALONE_GAME_DATA = "+json.dumps(payload,ensure_ascii=False,indent=2)+";\nwindow.GAME_KNOWLEDGE_COVERAGE = "+json.dumps(payload["coverage"],ensure_ascii=False)+";\n",encoding="utf-8")
    print(json.dumps({"status":"pass","mode":mode,"out":str(out)},ensure_ascii=False))
    return 0
if __name__=="__main__": raise SystemExit(main())
