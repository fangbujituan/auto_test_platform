"""
测试RequestFactory功能。

运行方式：
python test_request_factory.py
"""
from app.services.request_factory import RequestFactory


def test_get_request():
    """测试GET请求。"""
    print("=" * 60)
    print("测试GET请求")
    print("=" * 60)
    
    factory = RequestFactory(timeout=10)
    
    # 测试一个公开的API
    result = factory.execute(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts/1",
        headers={"Accept": "application/json"}
    )
    
    print(f"成功: {result['success']}")
    print(f"耗时: {result['duration']}秒")
    print(f"时间戳: {result['timestamp']}")
    
    if result['success']:
        print(f"\n状态码: {result['response']['status_code']}")
        print(f"响应大小: {result['response']['size']} bytes")
        print(f"响应体: {result['response']['body']}")
    else:
        print(f"\n错误类型: {result['error']['type']}")
        print(f"错误消息: {result['error']['message']}")
    
    factory.close()
    print()


def test_post_request():
    """测试POST请求。"""
    print("=" * 60)
    print("测试POST请求")
    print("=" * 60)
    
    factory = RequestFactory(timeout=10)
    
    result = factory.execute(
        method="POST",
        url="https://jsonplaceholder.typicode.com/posts",
        headers={"Content-Type": "application/json"},
        body={
            "title": "测试标题",
            "body": "测试内容",
            "userId": 1
        },
        body_type="json"
    )
    
    print(f"成功: {result['success']}")
    print(f"耗时: {result['duration']}秒")
    
    if result['success']:
        print(f"\n状态码: {result['response']['status_code']}")
        print(f"响应体: {result['response']['body']}")
    else:
        print(f"\n错误: {result['error']['message']}")
    
    factory.close()
    print()


def test_timeout():
    """测试超时处理。"""
    print("=" * 60)
    print("测试超时处理")
    print("=" * 60)
    
    factory = RequestFactory(timeout=1)  # 设置1秒超时
    
    # 使用一个会超时的URL
    result = factory.execute(
        method="GET",
        url="https://httpbin.org/delay/5"  # 延迟5秒响应
    )
    
    print(f"成功: {result['success']}")
    print(f"耗时: {result['duration']}秒")
    
    if not result['success']:
        print(f"\n错误类型: {result['error']['type']}")
        print(f"错误消息: {result['error']['message']}")
    
    factory.close()
    print()


def test_connection_error():
    """测试连接错误。"""
    print("=" * 60)
    print("测试连接错误")
    print("=" * 60)
    
    factory = RequestFactory()
    
    # 使用一个不存在的域名
    result = factory.execute(
        method="GET",
        url="http://this-domain-does-not-exist-12345.com"
    )
    
    print(f"成功: {result['success']}")
    print(f"耗时: {result['duration']}秒")
    
    if not result['success']:
        print(f"\n错误类型: {result['error']['type']}")
        print(f"错误消息: {result['error']['message']}")
    
    factory.close()
    print()


def test_validation():
    """测试响应验证。"""
    print("=" * 60)
    print("测试响应验证")
    print("=" * 60)
    
    factory = RequestFactory()
    
    result = factory.execute(
        method="GET",
        url="https://jsonplaceholder.typicode.com/posts/1"
    )
    
    if result['success']:
        # 验证状态码
        validation = factory.validate_response(
            result,
            expected_status=200,
            expected_body={"userId": 1}
        )
        
        print(f"验证通过: {validation['passed']}")
        if not validation['passed']:
            print(f"失败原因: {validation['failures']}")
    
    factory.close()
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("RequestFactory 功能测试")
    print("=" * 60 + "\n")
    
    try:
        test_get_request()
        test_post_request()
        test_timeout()
        test_connection_error()
        test_validation()
        
        print("=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
