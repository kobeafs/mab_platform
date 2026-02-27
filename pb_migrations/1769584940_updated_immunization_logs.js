/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2208481309")

  // update field
  collection.fields.addAt(3, new Field({
    "hidden": false,
    "id": "select4198493223",
    "maxSelect": 1,
    "name": "action_type",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "select",
    "values": [
      "Bleed",
      "Titer Check",
      "Primary",
      "Boost",
      "Final Boost"
    ]
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2208481309")

  // update field
  collection.fields.addAt(3, new Field({
    "hidden": false,
    "id": "select4198493223",
    "maxSelect": 1,
    "name": "action_type",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "select",
    "values": [
      "Immunization",
      "Bleed",
      "Titer Check"
    ]
  }))

  return app.save(collection)
})
