class_name Goblin
extends BaseEnemy
## A forest goblin.

signal attacked(target: Node)

const LOOT = preload("res://enemies/goblin/goblin_data.tres")
@export var aggro_range := 120.0
@export_range(0, 10)
var rage: int = 0
@onready var sprite: Sprite2D = $Sprite2D
var _state = "idle"

func _ready() -> void:
	pass

func attack(target: Node) -> void:
	attacked.emit(target)
