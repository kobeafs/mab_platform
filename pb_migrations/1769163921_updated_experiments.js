/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_3464712583")

  // update field
  collection.fields.addAt(3, new Field({
    "hidden": false,
    "id": "file687135939",
    "maxSelect": 1,
    "maxSize": 0,
    "mimeTypes": [],
    "name": "raw_data_file",
    "presentable": false,
    "protected": false,
    "required": false,
    "system": false,
    "thumbs": [],
    "type": "file"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_3464712583")

  // update field
  collection.fields.addAt(3, new Field({
    "hidden": false,
    "id": "file687135939",
    "maxSelect": 1,
    "maxSize": 0,
    "mimeTypes": [
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "text/csv",
      "image/png",
      "image/jpeg",
      "image/webp"
    ],
    "name": "raw_data_file",
    "presentable": false,
    "protected": false,
    "required": false,
    "system": false,
    "thumbs": [],
    "type": "file"
  }))

  return app.save(collection)
})
