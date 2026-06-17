#!/bin/bash
cd "$(dirname "$0")"
git init
git config user.email "clzmyiz@gmail.com"
git config user.name "heekeunlee"
git branch -M main
git remote remove origin 2>/dev/null
git remote add origin https://github.com/heekeunlee/seoul_apt.git
git add .
git commit -m "초기: 서울 아파트 실거래가 대시보드"
git push -u origin main
echo "완료! https://heekeunlee.github.io/seoul_apt"
