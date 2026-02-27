/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_3615662572")

  // add field
  collection.fields.addAt(5, new Field({
    "hidden": false,
    "id": "json2209810907",
    "maxSize": 0,
    "name": "change_snapshot",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "json"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_3615662572")

  // remove field
  collection.fields.removeById("json2209810907")

  return app.save(collection)
})
