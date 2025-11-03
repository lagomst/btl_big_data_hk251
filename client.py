import httpx


url = "http://127.0.0.1:9999/v1/rag/completions"
headers = {
    "accept": "application/json",
    "Content-Type": "application/json",
}
data = {
    "model": "test_cv",
    "prompt": "Give me the contact information of Thanh Hoa and her/his technical skills.",
    "max_tokens": 5000,
    "temperature": 1,
    "stream": True
}

with httpx.stream("POST", url, headers=headers, json=data, timeout=10.0) as response:
    for line in response.iter_lines():
        if line:
            print(line)

# url = "http://127.0.0.1:9999/v1/rag/query-stream"
# headers = {
#     "accept": "application/json",
#     "Content-Type": "application/json",
# }
# data = {
#     "model": "test_cv",
#     "prompt": "Give me the contact information of Thanh Hoa and her/his technical skills.",
#     "max_tokens": 5000,
#     "temperature": 1,
#     "stream": True
# }

# with httpx.stream("POST", url, headers=headers, json=data, timeout=10.0) as response:
#     for line in response.iter_lines():
#         if line:
#             print(line)
