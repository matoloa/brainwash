import time

class MyClass():
    def __init__(self, name):
        self.name = name
    
    def sayHi(self):
        print(f'hi from MyClass {self.name}')
        

myinstance = MyClass('johnny')

def newMethod(self):
    print(f'hi from MyClass after instantiation {self.name}')

MyClass.newMethod = newMethod

time.sleep(2)