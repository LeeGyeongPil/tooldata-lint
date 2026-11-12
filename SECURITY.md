# 보안 정책 / Security policy

보안 취약점을 발견하셨다면 **공개 이슈 대신** 이 레포의 **Security → Report a vulnerability**(비공개 취약점 신고)로 알려 주세요. 확인 후 답변드리고, 고친 버전을 릴리스하면서 함께 안내합니다.

If you find a security issue, please **do not open a public issue**. Use **Security → Report a vulnerability** in this repository to report it privately. We will reply after checking and announce the fix with a release.

이 도구는 로컬 파일만 읽는 명령줄 프로그램입니다. 네트워크에 접속하지 않고 포트도 열지 않으며, 스키마의 `$ref` 원격 주소도 내려받지 않습니다. / This is a command-line tool that only reads local files. It makes no network connections, opens no ports and never downloads remote `$ref` schemas.
