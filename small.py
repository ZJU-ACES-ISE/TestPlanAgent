from functools import wraps  
  
def my_decorator(func):  
    # @wraps(func)  
    def wrapper(*args, **kwargs):  
        """ xx """
        print(f"Something is happening before the function {func.__name__} is called.")  
        result = func(*args, **kwargs)  
        print(f"Something is happening after the function {func.__name__} is called.")  
        return result  
    return wrapper  
  
@my_decorator  
def say_hello(name):  
    """Greet the user by name."""  
    return f"Hello {name}!"  
  
print(say_hello.__name__)  # 输出: say_hello  
print(say_hello.__doc__)   # 输出: Greet the user by name.  
  
# 如果没有使用@wraps，则输出将是wrapper和wrapper的文档字符串（如果有的话）