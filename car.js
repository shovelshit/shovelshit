async function onRequest(context, request) {
  var body = ''
  if (request.path == '/check' || request.path == '/remaining_time') {
    body = JSON.stringify({
      "activated": true,
      "code": "AAAD-9488-EN7F-9Y9S-WX",
      "remaining_time": {
        "days": 99999,
        "hours": 0,
        "minutes": 0,
        "seconds": 0,
        "total_seconds": 0
      },
      "expire_time": "2099-01-01T00:00:00.000000+08:00",
      "activation_time": "2099-01-01T00:00:00.000000+08:00",
      "is_expired": false,
      "message": "剩余 100000 天",
      "issued_at": "2099-01-01T00:00:00.000000+08:00",
      "expire_at": "2099-01-01T00:00:00.000000+08:00",
      "nonce": "8cca1d09494d47bc8dcc327f38e5746d",
      "license_nonce": "8cca1d09494d47bc8dcc327f38e5746d",
      "license_token": "{\"activation_time\":\"2026-04-22T14:04:34.579088+08:00\",\"code\":\"AAAD-9488-EN7F-9Y9S-WX\",\"device_id\":\"L6T7752D2PE012575\",\"expire_at\":\"2026-04-29T14:04:34.579123+08:00\",\"expire_time\":\"2026-04-29T14:04:34.579123+08:00\",\"is_expired\":false,\"issued_at\":\"2026-04-22T21:14:06.924782+08:00\",\"key_id\":\"main\",\"nonce\":\"8cca1d09494d47bc8dcc327f38e5746d\",\"project_id\":\"xb_launcher\",\"state\":\"active\",\"v\":1}",
      "license_sig": "FQm/EsFNL48Q5odBqqSb/yboaUQg/J/ANohtQF5kUKWXkEAHT4/0+TPNB2VpXSw6GbiDZyJHvl3yBf7TFMA1lOvcHxZwoUQCiIxrweQBfXrmNDpfQiTDDyxVdC8x1Bbrl7wZKhPg8gZxD4AZFrW0AEhEUBsaNCzi4RZ0g/VHxg7N5r8/zvQEYzcTI+f+OiY1GHFs+jhknTBggLot6prEiAwDlIpyMm+qzXGBRy3SYbToR3Hg9YDrC51m980puKWx5IQd9gPzhIPA6V5h4UXOtz/3ZjAJdYR1M4lYs4L0bo/T4sB9B55noQMjsI99M8IFyq34t6aApv5VZLgjAPMSDA==",
      "license_key_id": "main"
    })
  } else if (request.path == '/check_signature') {
    body = JSON.stringify({
      "success": true,
      "message": "签名验证通过",
      "issued_at": "2026-04-23T22:34:58.704763+08:00",
      "nonce": "97231a39eb44d48313f2e3530edae4e2",
      "verify_token": "{\"device_id\":\"L6T7752D2PE012575\",\"issued_at\":\"2026-04-23T22:34:58.704763+08:00\",\"key_id\":\"main\",\"nonce\":\"97231a39eb44d48313f2e3530edae4e2\",\"package_name\":\"com.xiaoba.launcher\",\"project_id\":\"xb_launcher\",\"signature\":\"1A2680117DEDD146FAAE56184042FDF42ED164D96D8D60210A5C7BD3ADF9ED76\",\"success\":true,\"v\":1,\"version_code\":206500}",
      "verify_sig": "PPohKLC69oDKCXOH6JLtOmD0BQpT9aTNfRKXzlWZrvK9fcIbDzLBlmobmyMik1a8MeDxTB9PPtrPlgWd4eSYnn4e60dnJ6rzfaYMEsygxiXJM658fJPoP9HNsYODD/cdJqJTQj09RD7zxoQnypOr5to+0wB3GiZr2ggS9Y+FnOyvFkn0ylZFS/cjpkOf9c+ZGJxO6Hhheb4kKve7X9jDJLJib+16VexrhsLZ3RGcqv+eEF07MKOtPdL2/XFzk3oNgoxpHk4ANiJbm73oh1/pCKaou94hvGGlXfnYG45AV8WGyiz5hR79hXcGqyLyAB4/7SEZR305IlzWbnt08u24UQ==",
      "license_key_id": "main"
    })
  } else {
    body = JSON.stringify({
      'message': "无需处理"
    })
  };
  var response = {
    statusCode: 200,
    body: body,
    headers: {
      'Content-Type': 'application/json'
    }
  };
  return response;
}
