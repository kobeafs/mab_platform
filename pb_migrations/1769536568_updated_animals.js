/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_121574967")

  // add field
  collection.fields.addAt(7, new Field({
    "hidden": false,
    "id": "date2502384312",
    "max": "",
    "min": "",
    "name": "start_date",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "date"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_121574967")

  // remove field
  collection.fields.removeById("date2502384312")

  return app.save(collection)
})
