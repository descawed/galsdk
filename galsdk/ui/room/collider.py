import tkinter as tk
from tkinter import ttk

from galsdk.coords import Dimension
from galsdk.module import ColliderType, CircleCollider, RectangleCollider, TriangleCollider
from galsdk.room import CircleColliderObject, RectangleColliderObject, TriangleColliderObject, WallColliderObject
from galsdk.ui.room.replaceable import Replaceable


ColliderObject = CircleColliderObject | RectangleColliderObject | TriangleColliderObject | WallColliderObject


class ColliderEditor(ttk.Frame):
    def __init__(self, collider: Replaceable[ColliderObject], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.collider = collider
        self.options = ['Wall', 'Rectangle', 'Triangle', 'Circle']

        match collider.object:
            case WallColliderObject():
                self.type = ColliderType.WALL
            case CircleColliderObject():
                self.type = ColliderType.CIRCLE
            case RectangleColliderObject():
                self.type = ColliderType.RECTANGLE
            case TriangleColliderObject():
                self.type = ColliderType.TRIANGLE
            case _:
                raise TypeError('Provided object was not a collider')

        self.type_var = tk.StringVar(self, self.options[self.type])
        type_label = ttk.Label(self, text='Type:', anchor=tk.W)
        type_input = ttk.OptionMenu(self, self.type_var, self.type_var.get(), *self.options,
                                    command=self.on_change_type)
        validator = (self.register(self.validate), '%P')

        self.x_var = tk.StringVar(self)
        self.x_var.trace_add('write', lambda *_: self.on_change_pos('x'))
        self.x_label = ttk.Label(self, text='X:', anchor=tk.W)
        self.x_input = ttk.Entry(self, textvariable=self.x_var, validate='all', validatecommand=validator)

        self.z_var = tk.StringVar(self)
        self.z_var.trace_add('write', lambda *_: self.on_change_pos('z'))
        self.z_label = ttk.Label(self, text='Z:', anchor=tk.W)
        self.z_input = ttk.Entry(self, textvariable=self.z_var, validate='all', validatecommand=validator)

        type_label.grid(row=0, column=0)
        type_input.grid(row=0, column=1)

        self.triangle_p1_x_var = tk.StringVar(self)
        self.triangle_p1_x_var.trace_add('write', lambda *_: self.on_change_tri_point('p1', 'x'))
        self.triangle_p2_x_var = tk.StringVar(self)
        self.triangle_p2_x_var.trace_add('write', lambda *_: self.on_change_tri_point('p2', 'x'))
        self.triangle_p3_x_var = tk.StringVar(self)
        self.triangle_p3_x_var.trace_add('write', lambda *_: self.on_change_tri_point('p3', 'x'))
        self.triangle_p1_z_var = tk.StringVar(self)
        self.triangle_p1_z_var.trace_add('write', lambda *_: self.on_change_tri_point('p1', 'z'))
        self.triangle_p2_z_var = tk.StringVar(self)
        self.triangle_p2_z_var.trace_add('write', lambda *_: self.on_change_tri_point('p2', 'z'))
        self.triangle_p3_z_var = tk.StringVar(self)
        self.triangle_p3_z_var.trace_add('write', lambda *_: self.on_change_tri_point('p3', 'z'))
        self.rectangle_width_var = tk.StringVar(self)
        self.rectangle_width_var.trace_add('write', lambda *_: self.on_change_rect_size('width'))
        self.rectangle_height_var = tk.StringVar(self)
        self.rectangle_height_var.trace_add('write', lambda *_: self.on_change_rect_size('height'))
        self.circle_radius_var = tk.StringVar(self)
        self.circle_radius_var.trace_add('write', lambda *_: self.on_change_radius())

        self.triangle_p1_x_label = ttk.Label(self, text='X1:', anchor=tk.W)
        self.triangle_p1_x_input = ttk.Entry(self, textvariable=self.triangle_p1_x_var, validate='all',
                                             validatecommand=validator)
        self.triangle_p1_z_label = ttk.Label(self, text='Z1:', anchor=tk.W)
        self.triangle_p1_z_input = ttk.Entry(self, textvariable=self.triangle_p1_z_var, validate='all',
                                             validatecommand=validator)
        self.triangle_p2_x_label = ttk.Label(self, text='X2:', anchor=tk.W)
        self.triangle_p2_x_input = ttk.Entry(self, textvariable=self.triangle_p2_x_var, validate='all',
                                             validatecommand=validator)
        self.triangle_p2_z_label = ttk.Label(self, text='Z2:', anchor=tk.W)
        self.triangle_p2_z_input = ttk.Entry(self, textvariable=self.triangle_p2_z_var, validate='all',
                                             validatecommand=validator)
        self.triangle_p3_x_label = ttk.Label(self, text='X3:', anchor=tk.W)
        self.triangle_p3_x_input = ttk.Entry(self, textvariable=self.triangle_p3_x_var, validate='all',
                                             validatecommand=validator)
        self.triangle_p3_z_label = ttk.Label(self, text='Z3:', anchor=tk.W)
        self.triangle_p3_z_input = ttk.Entry(self, textvariable=self.triangle_p3_z_var, validate='all',
                                             validatecommand=validator)
        self.rectangle_width_label = ttk.Label(self, text='W:', anchor=tk.W)
        self.rectangle_width_input = ttk.Entry(self, textvariable=self.rectangle_width_var, validate='all',
                                               validatecommand=validator)
        self.rectangle_height_label = ttk.Label(self, text='H:', anchor=tk.W)
        self.rectangle_height_input = ttk.Entry(self, textvariable=self.rectangle_height_var, validate='all',
                                                validatecommand=validator)
        self.circle_radius_label = ttk.Label(self, text='R:', anchor=tk.W)
        self.circle_radius_input = ttk.Entry(self, textvariable=self.circle_radius_var, validate='all',
                                             validatecommand=validator)

        self.update_display()

    @staticmethod
    def validate(value: str) -> bool:
        if value == '':
            return True

        try:
            int(value)
            return True
        except ValueError:
            return False

    def toggle_triangle(self, show: bool):
        if show:
            self.x_label.grid_forget()
            self.x_input.grid_forget()
            self.z_label.grid_forget()
            self.z_input.grid_forget()
            self.triangle_p1_x_label.grid(row=1, column=0)
            self.triangle_p1_x_input.grid(row=1, column=1)
            self.triangle_p1_z_label.grid(row=2, column=0)
            self.triangle_p1_z_input.grid(row=2, column=1)
            self.triangle_p2_x_label.grid(row=3, column=0)
            self.triangle_p2_x_input.grid(row=3, column=1)
            self.triangle_p2_z_label.grid(row=4, column=0)
            self.triangle_p2_z_input.grid(row=4, column=1)
            self.triangle_p3_x_label.grid(row=5, column=0)
            self.triangle_p3_x_input.grid(row=5, column=1)
            self.triangle_p3_z_label.grid(row=6, column=0)
            self.triangle_p3_z_input.grid(row=6, column=1)
            self.triangle_p1_x_input.focus_force()
        else:
            self.triangle_p1_x_label.grid_forget()
            self.triangle_p1_x_input.grid_forget()
            self.triangle_p1_z_label.grid_forget()
            self.triangle_p1_z_input.grid_forget()
            self.triangle_p2_x_label.grid_forget()
            self.triangle_p2_x_input.grid_forget()
            self.triangle_p2_z_label.grid_forget()
            self.triangle_p2_z_input.grid_forget()
            self.triangle_p3_x_label.grid_forget()
            self.triangle_p3_x_input.grid_forget()
            self.triangle_p3_z_label.grid_forget()
            self.triangle_p3_z_input.grid_forget()
            self.circle_radius_label.grid_forget()
            self.circle_radius_input.grid_forget()

    def toggle_circle(self, show: bool):
        if show:
            self.x_label.grid(row=1, column=0)
            self.x_input.grid(row=1, column=1)
            self.z_label.grid(row=2, column=0)
            self.z_input.grid(row=2, column=1)
            self.circle_radius_label.grid(row=3, column=0)
            self.circle_radius_input.grid(row=3, column=1)
            self.x_input.focus_force()
        else:
            self.circle_radius_label.grid_forget()
            self.circle_radius_input.grid_forget()

    def toggle_rectangle(self, show: bool):
        if show:
            self.x_label.grid(row=1, column=0)
            self.x_input.grid(row=1, column=1)
            self.z_label.grid(row=2, column=0)
            self.z_input.grid(row=2, column=1)
            self.rectangle_width_label.grid(row=3, column=0)
            self.rectangle_width_input.grid(row=3, column=1)
            self.rectangle_height_label.grid(row=4, column=0)
            self.rectangle_height_input.grid(row=4, column=1)
            self.x_input.focus_force()
        else:
            self.rectangle_width_label.grid_forget()
            self.rectangle_width_input.grid_forget()
            self.rectangle_height_label.grid_forget()
            self.rectangle_height_input.grid_forget()

    def update_display(self):
        match self.type:
            case ColliderType.WALL | ColliderType.RECTANGLE:
                self.x_var.set(str(self.collider.object.x_pos.game_units))
                self.z_var.set(str(self.collider.object.z_pos.game_units))
                self.rectangle_width_var.set(str(self.collider.object.width.game_units))
                self.rectangle_height_var.set(str(self.collider.object.height.game_units))
                self.toggle_rectangle(True)
                self.toggle_triangle(False)
                self.toggle_circle(False)
            case ColliderType.TRIANGLE:
                p1 = self.collider.object.p1
                p2 = self.collider.object.p2
                p3 = self.collider.object.p3
                self.triangle_p1_x_var.set(str(p1.game_x))
                self.triangle_p1_z_var.set(str(p1.game_z))
                self.triangle_p2_x_var.set(str(p2.game_x))
                self.triangle_p2_z_var.set(str(p2.game_z))
                self.triangle_p3_x_var.set(str(p3.game_x))
                self.triangle_p3_z_var.set(str(p3.game_z))
                self.toggle_rectangle(False)
                self.toggle_triangle(True)
                self.toggle_circle(False)
            case ColliderType.CIRCLE:
                self.x_var.set(str(self.collider.object.position.game_x))
                self.z_var.set(str(self.collider.object.position.game_z))
                self.circle_radius_var.set(str(self.collider.object.radius.game_units))
                self.toggle_rectangle(False)
                self.toggle_triangle(False)
                self.toggle_circle(True)

    def on_change_pos(self, axis: str):
        new_value = int(getattr(self, f'{axis}_var').get() or '0')
        match self.type:
            case ColliderType.WALL | ColliderType.RECTANGLE:
                setattr(self.collider.object, f'{axis}_pos', Dimension(new_value, axis == 'x'))
            case ColliderType.CIRCLE:
                setattr(self.collider.object.position, f'game_{axis}', new_value)
        self.collider.object.update_position()

    def on_change_tri_point(self, point: str, axis: str):
        var = getattr(self, f'triangle_{point}_{axis}_var')
        setattr(getattr(self.collider.object, point), f'game_{axis}', int(var.get() or '0'))
        self.collider.object.recalculate_center()
        self.collider.object.update()

    def on_change_radius(self):
        radius = int(self.circle_radius_var.get() or '0')
        self.collider.object.radius.game_units = radius
        self.collider.object.update_model()

    def on_change_rect_size(self, dimension: str):
        var = getattr(self, f'rectangle_{dimension}_var')
        var_dim = Dimension(int(var.get() or '0'), dimension == 'width')
        getattr(self.collider.object, f'set_{dimension}')(var_dim)
        self.collider.object.update()

    def on_change_type(self, _=None):
        type_string = self.type_var.get()
        new_type = ColliderType(self.options.index(type_string))
        if self.type == new_type:
            return

        self.type = new_type
        x = self.collider.object.position.game_x
        z = self.collider.object.position.game_z
        name = self.collider.object.name

        match self.type:
            case ColliderType.WALL:
                bounds = RectangleCollider(x, z, 0, 0)
                self.collider.object = WallColliderObject(name, bounds)
            case ColliderType.RECTANGLE:
                bounds = RectangleCollider(x, z, 0, 0)
                self.collider.object = RectangleColliderObject(name, bounds)
            case ColliderType.TRIANGLE:
                bounds = TriangleCollider(x, z, x, z, x, z)
                self.collider.object = TriangleColliderObject(name, bounds)
            case ColliderType.CIRCLE:
                bounds = CircleCollider(x, z, 0)
                self.collider.object = CircleColliderObject(name, bounds)

        self.update_display()
