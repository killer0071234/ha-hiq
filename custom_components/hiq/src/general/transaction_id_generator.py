from ..general.errors import TransactionIdGeneratorError


def transaction_id_generator(from_id, to_id, step=1):
    if from_id == to_id:
        raise TransactionIdGeneratorError("`from_id` can't be equal to `to_id`")

    t_id = from_id

    while True:
        yield t_id

        t_id += step
        if t_id == to_id:
            t_id = from_id
