@router.delete("/delete/{transcription_id}")
async def delete_transcription(
    transcription_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    transcription = db.query(Transcription).filter(
        Transcription.id == transcription_id,
        Transcription.user_id == current_user["id"]
    ).first()

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found.")

    db.delete(transcription)
    db.commit()

    return {"message": "Transcription deleted successfully"}