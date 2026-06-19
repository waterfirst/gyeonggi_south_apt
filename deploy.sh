#!/bin/bash
# 서울 아파트 대시보드 배포 스크립트
# 사용법: sh deploy.sh
cd "$(dirname "$0")"
MSG="업데이트: $(date +'%Y-%m-%d %H:%M')"
git add .
git diff --staged --quiet && echo "변경사항 없음" && exit 0
git commit -m "$MSG"
git push
echo "✅ 배포 완료 → https://heekeunlee.github.io/seoul_apt"
