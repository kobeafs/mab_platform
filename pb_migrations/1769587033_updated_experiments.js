/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_3464712583")

  // add field
  collection.fields.addAt(6, new Field({
    "hidden": false,
    "id": "select1045770772",
    "maxSelect": 1,
    "name": "exp_type",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "select",
    "values": [
      "ELISA",
      "WB",
      "SPR",
      "Seq"
    ]
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_3464712583")

  // remove field
  collection.fields.removeById("select1045770772")

  return app.save(collection)
})
